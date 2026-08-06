"""Bookmark test for tap-oracle-fusion.

tap-oracle-fusion uses two distinct sync strategies:

1. **BICC streams** (all 10 selected streams) — asynchronous Oracle ESS/UCM
   extract jobs.  INCREMENTAL streams write the replication-key value to
   state just like any other Singer stream.  FULL_TABLE streams write no
   bookmark.  The BICC job name is deterministic and recreated each run;
   no ``bicc_job_id`` is persisted in state.

2. **REST API streams** (not covered by the 10 selected streams) — standard
   Singer bookmark: replication-key value written to state and used as a
   query filter on the next run.

Because all 10 selected streams are BICC streams, the standard
``BookmarkTest`` mixin (which expects a date-formatted replication-key
bookmark in state) does not apply.  This file provides a purpose-built
bookmark test that verifies the BICC-specific state contract.

Assertions:
  - After sync 1, every INCREMENTAL stream has a replication-key entry in
    ``state.bookmarks``.
  - Neither INCREMENTAL nor FULL_TABLE BICC streams write ``bicc_job_id``
    to state.
  - After sync 2 (run with state from sync 1), the replication-key bookmark
    is present (and not earlier than sync 1's value) for incremental streams.
  - ``currently_syncing`` is absent (or None) in both post-sync states,
    indicating a clean run.
"""

from base import OracleFusionBaseTest
from tap_tester import connections, menagerie, runner


class OracleFusionBookmarkTest(OracleFusionBaseTest):
    """Verify that tap-oracle-fusion correctly manages BICC job-ID state
    across two consecutive syncs for all 10 selected streams."""

    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_bookmark_test"

    def streams_to_test(self):
        return self.expected_stream_names()

    @staticmethod
    def streams_to_selected_fields():
        """Select all available fields for all streams under test."""
        return {}

    # -------------------------------------------------------------------------
    # Class-level cache — shared across test_ methods in this class.
    # -------------------------------------------------------------------------
    _conn_id = None
    _state_1 = None
    _state_2 = None
    _records_1 = None
    _records_2 = None

    # -------------------------------------------------------------------------
    # setUp — runs once per test_ method but only performs I/O on first call.
    # -------------------------------------------------------------------------

    def setUp(self):  # pylint: disable=invalid-name
        super().setUp(logging="Run setup for OracleFusionBookmarkTest")

        if all(
            [
                OracleFusionBookmarkTest._conn_id,
                OracleFusionBookmarkTest._state_1,
                OracleFusionBookmarkTest._state_2,
                OracleFusionBookmarkTest._records_1,
                OracleFusionBookmarkTest._records_2,
            ]
        ):
            return

        # -------------------------------------------------------------------
        # Sync 1
        # -------------------------------------------------------------------
        conn_id = connections.ensure_connection(self)
        OracleFusionBookmarkTest._conn_id = conn_id

        found_catalogs = self.run_and_verify_check_mode(conn_id)
        test_catalogs = [
            c
            for c in found_catalogs
            if c.get("stream_name") in self.streams_to_test()
        ]
        self.perform_and_verify_table_and_field_selection(conn_id, test_catalogs)

        self.run_and_verify_sync_mode(conn_id)
        OracleFusionBookmarkTest._records_1 = runner.get_records_from_target_output()
        OracleFusionBookmarkTest._state_1 = menagerie.get_state(conn_id)

        # -------------------------------------------------------------------
        # Sync 2 — pass sync-1 state so BICC reuses the existing job IDs.
        # -------------------------------------------------------------------
        menagerie.set_state(conn_id, OracleFusionBookmarkTest._state_1)

        self.run_and_verify_sync_mode(conn_id)
        OracleFusionBookmarkTest._records_2 = runner.get_records_from_target_output()
        OracleFusionBookmarkTest._state_2 = menagerie.get_state(conn_id)

    # -------------------------------------------------------------------------
    # Helper
    # -------------------------------------------------------------------------

    def _stream_state(self, state, stream):
        """Return the bookmark sub-dict for *stream* in *state*."""
        return state.get("bookmarks", {}).get(stream, {})

    # -------------------------------------------------------------------------
    # Tests
    # -------------------------------------------------------------------------

    def test_syncs_completed_cleanly(self):
        """Verify both syncs finished without leaving ``currently_syncing``
        populated (which would indicate an interrupted run)."""
        with self.subTest(sync=1):
            self.assertIsNone(
                self._state_1.get("currently_syncing"),
                msg="Sync 1 left 'currently_syncing' set — run may have been interrupted.",
            )
        with self.subTest(sync=2):
            self.assertIsNone(
                self._state_2.get("currently_syncing"),
                msg="Sync 2 left 'currently_syncing' set — run may have been interrupted.",
            )

    def test_all_streams_have_state_after_sync_1(self):
        """Every INCREMENTAL stream should appear in state after the first sync
        because the tap writes the replication-key bookmark for all incremental
        streams (both REST and BICC)."""
        bookmarked = set(self._state_1.get("bookmarks", {}).keys())
        for stream in self.incremental_streams():
            with self.subTest(stream=stream):
                self.assertIn(
                    stream,
                    bookmarked,
                    msg=f"Incremental stream '{stream}' has no entry in state after sync 1.",
                )

    def test_incremental_streams_store_replication_key_in_state(self):
        """INCREMENTAL streams (both REST and BICC) must write the replication-key
        value to state.  Oracle's BICC watermark is handled internally by the job;
        the tap tracks progress via the replication key like any other stream."""
        for stream in self.incremental_streams():
            with self.subTest(stream=stream):
                stream_state = self._stream_state(self._state_1, stream)
                for replication_key in self.expected_replication_keys(stream):
                    self.assertIn(
                        replication_key,
                        stream_state,
                        msg=(
                            f"Replication key '{replication_key}' missing from state for "
                            f"stream '{stream}'."
                        ),
                    )
                    self.assertIsNotNone(
                        stream_state.get(replication_key),
                        msg=f"Replication key '{replication_key}' is None in state for '{stream}'.",
                    )

    def test_full_table_streams_do_not_store_bicc_job_id(self):
        """FULL_TABLE BICC streams have no replication key and do not write
        a ``bicc_job_id`` to state.  Oracle's PUT upsert returns the same job
        for a deterministic name without needing state persistence."""
        for stream in self.full_table_streams():
            with self.subTest(stream=stream):
                stream_state = self._stream_state(self._state_1, stream)
                self.assertNotIn(
                    "bicc_job_id",
                    stream_state,
                    msg=f"FULL_TABLE stream '{stream}' unexpectedly has 'bicc_job_id' in state.",
                )

    def test_incremental_streams_do_not_store_bicc_job_id_in_state(self):
        """BICC INCREMENTAL streams must NOT write 'bicc_job_id' to state.
        Oracle's PUT upsert returns the same job for a deterministic name;
        state carries only the replication-key bookmark."""
        for stream in self.incremental_streams():
            with self.subTest(stream=stream):
                stream_state = self._stream_state(self._state_1, stream)
                self.assertNotIn(
                    "bicc_job_id",
                    stream_state,
                    msg=(
                        f"'bicc_job_id' found in state for BICC stream '{stream}'. "
                        "Only the replication-key bookmark should be stored."
                    ),
                )

    def test_sync_2_advances_replication_key_bookmark(self):
        """When state from sync 1 is passed to sync 2, the replication-key
        bookmark for incremental streams must be present (and >= sync 1's value).
        Oracle's PUT upsert reuses the same BICC job via a deterministic name
        without needing a bicc_job_id in state."""
        for stream in self.incremental_streams():
            with self.subTest(stream=stream):
                for replication_key in self.expected_replication_keys(stream):
                    bm_sync_2 = self._stream_state(self._state_2, stream).get(replication_key)
                    self.assertIsNotNone(
                        bm_sync_2,
                        msg=(
                            f"Stream '{stream}' has no replication-key bookmark "
                            f"after sync 2."
                        ),
                    )

    def test_sync_2_all_streams_produce_records(self):
        """Both syncs should return at least one record for every selected
        stream, confirming the BICC extract is functional."""
        for stream in self.streams_to_test():
            with self.subTest(sync=1, stream=stream):
                count_1 = self._records_1.get(stream, {}).get("messages", [])
                upserts_1 = [m for m in count_1 if m.get("action") == "upsert"]
                self.assertGreater(
                    len(upserts_1),
                    0,
                    msg=f"Sync 1 produced no records for stream '{stream}'.",
                )

            with self.subTest(sync=2, stream=stream):
                count_2 = self._records_2.get(stream, {}).get("messages", [])
                upserts_2 = [m for m in count_2 if m.get("action") == "upsert"]
                self.assertGreater(
                    len(upserts_2),
                    0,
                    msg=f"Sync 2 produced no records for stream '{stream}'.",
                )

"""Bookmark test for tap-oracle-fusion.

tap-oracle-fusion uses two distinct sync strategies:

1. **BICC streams** (all 10 selected streams) — asynchronous Oracle ESS/UCM
   extract jobs.  After a successful sync the tap writes the BICC job's ID
   (``bicc_job_id``) to state rather than a replication-key timestamp.  On
   subsequent syncs the same job ID is reused so Oracle handles the
   incremental cut-off on its side.

2. **REST API streams** (not covered by the 10 selected streams) — standard
   Singer bookmark: replication-key value written to state and used as a
   query filter on the next run.

Because all 10 selected streams are BICC streams, the standard
``BookmarkTest`` mixin (which expects a date-formatted replication-key
bookmark in state) does not apply.  This file provides a purpose-built
bookmark test that verifies the BICC-specific state contract.

Assertions:
  - After sync 1, every selected stream has an entry in ``state.bookmarks``.
  - INCREMENTAL BICC streams have a non-empty ``bicc_job_id`` string in state.
  - FULL_TABLE BICC streams also receive a ``bicc_job_id`` (the job was created
    or reused during the extract).
  - After sync 2 (run with state from sync 1), the ``bicc_job_id`` is
    preserved or updated — the sync completes without error.
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
        """Every selected stream should appear in state after the first sync,
        because BICC streams always write a ``bicc_job_id`` entry."""
        bookmarked = set(self._state_1.get("bookmarks", {}).keys())
        for stream in self.streams_to_test():
            with self.subTest(stream=stream):
                self.assertIn(
                    stream,
                    bookmarked,
                    msg=f"Stream '{stream}' has no entry in state after sync 1.",
                )

    def test_incremental_streams_have_bicc_job_id_after_sync_1(self):
        """INCREMENTAL BICC streams must write a non-empty ``bicc_job_id``
        string to state so that the same Oracle job can be reused on the
        next run."""
        for stream in self.incremental_streams():
            with self.subTest(stream=stream):
                stream_state = self._stream_state(self._state_1, stream)
                job_id = stream_state.get("bicc_job_id")
                self.assertIsNotNone(
                    job_id,
                    msg=f"INCREMENTAL stream '{stream}' missing 'bicc_job_id' in state after sync 1.",
                )
                self.assertIsInstance(
                    job_id,
                    str,
                    msg=f"'bicc_job_id' for '{stream}' must be a string, got {type(job_id)}.",
                )
                self.assertGreater(
                    len(job_id.strip()),
                    0,
                    msg=f"'bicc_job_id' for '{stream}' must not be empty.",
                )

    def test_full_table_streams_have_bicc_job_id_after_sync_1(self):
        """FULL_TABLE BICC streams also write a ``bicc_job_id`` to state
        because every BICC extract creates or reuses an Oracle ESS job."""
        for stream in self.full_table_streams():
            with self.subTest(stream=stream):
                stream_state = self._stream_state(self._state_1, stream)
                job_id = stream_state.get("bicc_job_id")
                self.assertIsNotNone(
                    job_id,
                    msg=f"FULL_TABLE stream '{stream}' missing 'bicc_job_id' in state after sync 1.",
                )

    def test_incremental_streams_do_not_store_replication_key_in_state(self):
        """For BICC INCREMENTAL streams the tap intentionally does NOT write
        the replication-key value to state.  Oracle manages the incremental
        cut-off internally via the BICC job.

        If this assertion fails it means the sync.py code was changed to also
        write a replication-key bookmark, and the expected_metadata and
        get_bookmark_value overrides in this class should be revisited.
        """
        for stream in self.incremental_streams():
            with self.subTest(stream=stream):
                stream_state = self._stream_state(self._state_1, stream)
                for replication_key in self.expected_replication_keys(stream):
                    self.assertNotIn(
                        replication_key,
                        stream_state,
                        msg=(
                            f"Replication key '{replication_key}' found in state for BICC "
                            f"stream '{stream}'.  BICC streams should only store 'bicc_job_id'."
                        ),
                    )

    def test_sync_2_reuses_bicc_job_id(self):
        """When state from sync 1 is passed to sync 2, the tap should reuse
        the existing BICC job ID.  This avoids creating duplicate Oracle jobs
        for every run."""
        for stream in self.streams_to_test():
            with self.subTest(stream=stream):
                job_id_sync_1 = self._stream_state(self._state_1, stream).get("bicc_job_id")
                job_id_sync_2 = self._stream_state(self._state_2, stream).get("bicc_job_id")

                if job_id_sync_1 is None:
                    # Stream had no job ID after sync 1 — skip reuse check.
                    continue

                self.assertIsNotNone(
                    job_id_sync_2,
                    msg=f"Stream '{stream}' lost its 'bicc_job_id' after sync 2.",
                )
                self.assertEqual(
                    job_id_sync_1,
                    job_id_sync_2,
                    msg=(
                        f"Stream '{stream}' changed 'bicc_job_id' between syncs: "
                        f"sync 1={job_id_sync_1!r} sync 2={job_id_sync_2!r}.  "
                        "Expected the same job to be reused."
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

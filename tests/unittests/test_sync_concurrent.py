"""Tests for max_concurrent_streams in tap_oracle_fusion.sync."""
import importlib
import threading
import time
import unittest
from unittest import mock

import singer
from singer import metadata
from singer.catalog import CatalogEntry, Schema

from tap_oracle_fusion.bicc_extract import ExtractError
from tap_oracle_fusion.schema import ENTITY_SET_METADATA_KEY

sync_module = importlib.import_module("tap_oracle_fusion.sync")

CONFIG = {"base_url": "https://example", "start_date": "2020-01-01T00:00:00Z"}


def _entry(stream_name, datastore):
    mdata = metadata.write(
        metadata.new(), (), ENTITY_SET_METADATA_KEY, f"biacm/rest/meta/datastores/{datastore}"
    )
    return CatalogEntry(
        stream=stream_name,
        tap_stream_id=stream_name,
        key_properties=[],
        schema=Schema.from_dict({"type": "object", "properties": {"Id": {"type": ["null", "string"]}}}),
        metadata=metadata.to_list(mdata),
    )


def _catalog(pairs):
    entries = {name: _entry(name, datastore) for name, datastore in pairs}
    catalog = mock.Mock()
    catalog.get_selected_streams.return_value = [mock.Mock(tap_stream_id=n) for n, _ in pairs]
    catalog.get_stream.side_effect = lambda stream_id: entries[stream_id]
    return catalog


class _FakeBICC:
    def __init__(self, barrier=None, fail_on=None, delay=0.0):
        self.barrier = barrier
        self.fail_on = fail_on
        self.delay = delay
        self._lock = threading.Lock()
        self.in_flight = 0
        self.max_in_flight = 0

    @staticmethod
    def datastore_slug(datastore):
        return datastore.lower()

    def create_bicc_job(self, datastore, initial_extract_date, job_name=None):
        return f"job-{datastore}"

    def run_extract_to_rows(self, datastore, job_id, **_kwargs):
        with self._lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.barrier:
                self.barrier.wait(timeout=5)
            if datastore == self.fail_on:
                raise ExtractError("boom")
            time.sleep(self.delay)
        finally:
            with self._lock:
                self.in_flight -= 1
        return iter([{"Id": f"{datastore}-{i}"} for i in range(2)]), {}


def _run(config, pairs, fake):
    records, states = [], []
    state = {}
    with mock.patch.object(sync_module, "BICCExtractClient", return_value=fake), \
            mock.patch.object(sync_module, "OracleClient"), \
            mock.patch.object(singer, "write_schema"), \
            mock.patch.object(singer, "write_state", side_effect=lambda s: states.append(dict(s))), \
            mock.patch.object(singer, "write_record", side_effect=lambda n, r: records.append((n, r))):
        sync_module.sync({**CONFIG, **config}, _catalog(pairs), state)
    return records, state


PAIRS = [(f"s{i}", f"DS.Store{i}") for i in range(4)]


class TestMaxConcurrentStreamsConfig(unittest.TestCase):
    def test_default_is_sequential(self):
        self.assertEqual(sync_module._get_max_concurrent_streams({}), 1)

    def test_values_are_clamped(self):
        get = sync_module._get_max_concurrent_streams
        self.assertEqual(get({"max_concurrent_streams": 3}), 3)
        self.assertEqual(get({"max_concurrent_streams": "2"}), 2)
        self.assertEqual(get({"max_concurrent_streams": 0}), 1)
        self.assertEqual(get({"max_concurrent_streams": -5}), 1)
        self.assertEqual(get({"max_concurrent_streams": 99}), sync_module.MAX_CONCURRENT_STREAMS_LIMIT)

    def test_invalid_value_is_sequential(self):
        self.assertEqual(sync_module._get_max_concurrent_streams({"max_concurrent_streams": "many"}), 1)
        self.assertEqual(sync_module._get_max_concurrent_streams({"max_concurrent_streams": None}), 1)


class TestConcurrentSync(unittest.TestCase):
    def test_output_and_state_match_sequential(self):
        seq_records, seq_state = _run({}, PAIRS, _FakeBICC())
        par_records, par_state = _run({"max_concurrent_streams": 3}, PAIRS, _FakeBICC(delay=0.02))
        self.assertEqual(par_records, seq_records)
        self.assertEqual(par_state, seq_state)
        self.assertEqual(len(par_records), 8)

    def test_streams_are_prepared_concurrently(self):
        fake = _FakeBICC(barrier=threading.Barrier(2))
        records, _ = _run({"max_concurrent_streams": 2}, PAIRS, fake)
        self.assertEqual(len(records), 8)
        self.assertEqual(fake.max_in_flight, 2)

    def test_in_flight_is_bounded_by_the_limit(self):
        pairs = [(f"s{i}", f"DS.Store{i}") for i in range(8)]
        fake = _FakeBICC(delay=0.03)
        _run({"max_concurrent_streams": 2}, pairs, fake)
        self.assertLessEqual(fake.max_in_flight, 2)

    def test_sequential_by_default(self):
        fake = _FakeBICC(delay=0.01)
        _run({}, PAIRS, fake)
        self.assertEqual(fake.max_in_flight, 1)

    def test_failure_after_earlier_streams_emitted(self):
        fake = _FakeBICC(fail_on="DS.Store2", delay=0.01)
        records = []
        with mock.patch.object(sync_module, "BICCExtractClient", return_value=fake), \
                mock.patch.object(sync_module, "OracleClient"), \
                mock.patch.object(singer, "write_schema"), \
                mock.patch.object(singer, "write_state"), \
                mock.patch.object(singer, "write_record", side_effect=lambda n, r: records.append(n)):
            with self.assertRaises(ExtractError):
                sync_module.sync({**CONFIG, "max_concurrent_streams": 2}, _catalog(PAIRS), {})
        self.assertEqual(records, ["s0", "s0", "s1", "s1"])

    def test_shared_job_name_falls_back_to_sequential(self):
        pairs = [("a", "DS.Store"), ("b", "ds.store"), ("c", "DS.Other")]
        fake = _FakeBICC(delay=0.02)
        records, _ = _run({"max_concurrent_streams": 3}, pairs, fake)
        self.assertEqual(fake.max_in_flight, 1)
        self.assertEqual(len(records), 6)


if __name__ == "__main__":
    unittest.main()

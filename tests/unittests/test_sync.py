import importlib
import unittest
from unittest import mock

from singer import metadata
from singer.catalog import CatalogEntry, Schema
from tap_oracle_fusion.schema import ENTITY_SET_METADATA_KEY

sync_module = importlib.import_module("tap_oracle_fusion.sync")


def _build_catalog_entry(stream_name: str, oracle_path: str = "") -> CatalogEntry:
    mdata = metadata.new()
    if oracle_path:
        mdata = metadata.write(mdata, (), ENTITY_SET_METADATA_KEY, oracle_path)

    return CatalogEntry(
        stream=stream_name,
        tap_stream_id=stream_name,
        key_properties=[],
        schema=Schema.from_dict(
            {
                "type": "object",
                "properties": {
                    "Id": {"type": ["null", "string"]},
                },
            }
        ),
        metadata=metadata.to_list(mdata),
    )


class TestSyncPathResolution(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.sync.get_stream_resource_map")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_sync_uses_oracle_path_from_catalog_without_discovery_lookup(
        self,
        mock_client_cls,
        mock_get_stream_resource_map,
    ):
        mock_client = mock_client_cls.return_value
        mock_client.get_records.return_value = []

        entry = _build_catalog_entry(
            "worker",
            "biacm/rest/meta/datastores/FscmTopModelAM.Worker",
        )

        selected_stream = mock.Mock()
        selected_stream.tap_stream_id = "worker"

        catalog = mock.Mock()
        catalog.get_selected_streams.return_value = [selected_stream]
        catalog.get_stream.return_value = entry

        sync_module.sync({"base_url": "https://example", "start_date": "2020-01-01T00:00:00Z"}, catalog, {})

        mock_get_stream_resource_map.assert_not_called()
        mock_client.get_records.assert_called_once_with(
            "biacm/rest/meta/datastores/FscmTopModelAM.Worker",
            params={},
        )

    @mock.patch("tap_oracle_fusion.sync.get_stream_resource_map")
    @mock.patch("tap_oracle_fusion.sync.OracleClient")
    def test_sync_falls_back_to_stream_map_once_when_oracle_path_is_missing(
        self,
        mock_client_cls,
        mock_get_stream_resource_map,
    ):
        mock_client = mock_client_cls.return_value
        mock_client.get_records.return_value = []

        entry = _build_catalog_entry("worker")

        selected_stream = mock.Mock()
        selected_stream.tap_stream_id = "worker"

        catalog = mock.Mock()
        catalog.get_selected_streams.return_value = [selected_stream]
        catalog.get_stream.return_value = entry

        mock_get_stream_resource_map.return_value = {
            "worker": "biacm/rest/meta/datastores/FscmTopModelAM.Worker",
        }

        sync_module.sync({"base_url": "https://example", "start_date": "2020-01-01T00:00:00Z"}, catalog, {})

        mock_get_stream_resource_map.assert_called_once()
        mock_client.get_records.assert_called_once_with(
            "biacm/rest/meta/datastores/FscmTopModelAM.Worker",
            params={},
        )


if __name__ == "__main__":
    unittest.main()

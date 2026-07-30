"""Tests for tap_oracle_fusion.__init__ (do_discover, do_connection_check, main)."""
import importlib
import json
import sys
import unittest
from unittest import mock

init_module = importlib.import_module("tap_oracle_fusion")


class TestDoDiscover(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.json.dump")
    @mock.patch("tap_oracle_fusion.discover")
    def test_do_discover_calls_discover_and_dumps(self, mock_discover, mock_dump):
        fake_catalog = mock.Mock()
        fake_catalog.to_dict.return_value = {"streams": []}
        mock_discover.return_value = fake_catalog

        result = init_module.do_discover(config={"base_url": "https://example"})

        mock_discover.assert_called_once_with(config={"base_url": "https://example"})
        mock_dump.assert_called_once()
        self.assertEqual(result, fake_catalog)

    @mock.patch("tap_oracle_fusion.json.dump")
    @mock.patch("tap_oracle_fusion.discover")
    def test_do_discover_returns_catalog(self, mock_discover, _mock_dump):
        fake_catalog = mock.Mock()
        fake_catalog.to_dict.return_value = {}
        mock_discover.return_value = fake_catalog

        result = init_module.do_discover(config={})
        self.assertIs(result, fake_catalog)


class TestDoConnectionCheck(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.sys.exit")
    @mock.patch("tap_oracle_fusion.OracleClient")
    def test_connection_check_success_exits_0(self, mock_client_cls, mock_exit):
        mock_client = mock_client_cls.return_value
        mock_client.get.return_value = {"dataStores": []}

        init_module.do_connection_check(config={"base_url": "https://example"})

        mock_exit.assert_called_once_with(0)

    @mock.patch("tap_oracle_fusion.sys.exit")
    @mock.patch("tap_oracle_fusion.OracleClient")
    def test_connection_check_failure_exits_1(self, mock_client_cls, mock_exit):
        from tap_oracle_fusion.client import OracleClientError
        mock_client = mock_client_cls.return_value
        mock_client.get.side_effect = OracleClientError("connection refused")

        init_module.do_connection_check(config={"base_url": "https://example"})

        mock_exit.assert_called_once_with(1)


class TestMain(unittest.TestCase):
    @mock.patch("tap_oracle_fusion.do_discover")
    @mock.patch("tap_oracle_fusion.singer.utils.parse_args")
    def test_main_discover_mode(self, mock_parse_args, mock_do_discover):
        args = mock.Mock()
        args.discover = True
        args.catalog = None
        args.state = {}
        args.config = {"base_url": "https://example"}
        mock_parse_args.return_value = args

        init_module.main()

        mock_do_discover.assert_called_once_with(config=args.config)

    @mock.patch("tap_oracle_fusion.sync")
    @mock.patch("tap_oracle_fusion.singer.utils.parse_args")
    def test_main_sync_mode(self, mock_parse_args, mock_sync):
        args = mock.Mock()
        args.discover = False
        args.catalog = mock.Mock()
        args.state = {"bookmarks": {}}
        args.config = {"base_url": "https://example"}
        mock_parse_args.return_value = args

        init_module.main()

        mock_sync.assert_called_once_with(
            config=args.config, catalog=args.catalog, state=args.state
        )

    @mock.patch("tap_oracle_fusion.do_connection_check")
    @mock.patch("tap_oracle_fusion.singer.utils.parse_args")
    def test_main_connection_check_mode(self, mock_parse_args, mock_conn_check):
        args = mock.Mock()
        args.discover = False
        args.catalog = None
        args.state = None
        args.config = {"base_url": "https://example"}
        mock_parse_args.return_value = args

        init_module.main()

        mock_conn_check.assert_called_once_with(config=args.config)

    @mock.patch("tap_oracle_fusion.sync")
    @mock.patch("tap_oracle_fusion.singer.utils.parse_args")
    def test_main_state_defaults_to_empty_dict_when_none(self, mock_parse_args, mock_sync):
        args = mock.Mock()
        args.discover = False
        args.catalog = mock.Mock()
        args.state = None
        args.config = {"base_url": "https://example"}
        mock_parse_args.return_value = args

        init_module.main()

        call_kwargs = mock_sync.call_args[1]
        self.assertEqual(call_kwargs["state"], {})


if __name__ == "__main__":
    unittest.main()

"""Oracle Fusion tap entry point: discover and sync modes."""
import json
import sys

import singer
from tap_oracle_fusion.discover import discover, BICC_DATASTORES_PATH
from tap_oracle_fusion.client import OracleClient, OracleClientError
from tap_oracle_fusion.sync import sync

LOGGER = singer.get_logger()

REQUIRED_CONFIG_KEYS = [
    "base_url",
    "username",
    "password",
    "start_date",
]


def do_discover(config):
    """Run discover mode and emit catalog JSON to stdout."""
    LOGGER.info("Starting dynamic discover")
    catalog = discover(config=config)
    json.dump(catalog.to_dict(), sys.stdout, indent=2)
    LOGGER.info("Finished dynamic discover")
    return catalog


def do_connection_check(config):
    """Verify API connectivity and credentials. Exit 0 on success, 1 on failure."""
    try:
        client = OracleClient(config)
        client.get(BICC_DATASTORES_PATH, params={"limit": 1, "offset": 0})
        LOGGER.info("Connection check passed")
        sys.exit(0)
    except OracleClientError as exc:
        LOGGER.error("Connection check failed: %s", exc)
        sys.exit(1)


@singer.utils.handle_top_exception(LOGGER)
def main():
    """
    Run the tap
    """
    parsed_args = singer.utils.parse_args(REQUIRED_CONFIG_KEYS)
    state = parsed_args.state if parsed_args.state else {}

    if parsed_args.discover:
        do_discover(config=parsed_args.config)
        return

    if parsed_args.catalog:
        sync(config=parsed_args.config, catalog=parsed_args.catalog, state=state)
        return

    do_connection_check(config=parsed_args.config)


if __name__ == "__main__":
    main()

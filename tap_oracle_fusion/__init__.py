import json
import sys

import singer
from tap_oracle_fusion.discover import discover
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

    LOGGER.error("No mode selected. Use --discover or provide a catalog for sync.")
    sys.exit(1)


if __name__ == "__main__":
    main()

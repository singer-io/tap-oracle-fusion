"""Fetch all BICC datastore names from Oracle Fusion and write them to a file.

Environment variables:
    ORACLE_BASE_URL   - Oracle Fusion base URL (required)
    ORACLE_USERNAME   - Basic auth username (required)
    ORACLE_PASSWORD   - Basic auth password (required)
    OUTPUT_FILE       - Output file path (default: bicc_datastores.txt)
"""
import os
import sys
from datetime import datetime, timezone

import requests

BICC_DATASTORES_PATH = "biacm/rest/meta/datastores"
DEFAULT_OUTPUT_FILE = "bicc_datastores.txt"


def _env(key: str, required: bool = True) -> str:
    value = os.environ.get(key, "").strip()
    if required and not value:
        print(f"ERROR: environment variable '{key}' is required but not set.", file=sys.stderr)
        sys.exit(1)
    return value


def fetch_datastores(base_url: str, username: str, password: str) -> list[str]:
    url = f"{base_url.rstrip('/')}/{BICC_DATASTORES_PATH}"
    print(f"Fetching: {url}")
    response = requests.get(
        url,
        auth=(username, password),
        headers={"Accept": "application/json"},
        timeout=300,
    )
    response.raise_for_status()
    payload = response.json()

    # Handle both list response and wrapped object response
    if isinstance(payload, list):
        entries = payload
    else:
        entries = None
        for key in ("dataStores", "datastores", "items", "data", "results"):
            if isinstance(payload.get(key), list):
                entries = payload[key]
                break
        if entries is None:
            print(f"ERROR: unexpected response shape: {list(payload.keys())}", file=sys.stderr)
            sys.exit(1)

    names: list[str] = []
    for entry in entries:
        if isinstance(entry, str):
            name = entry.strip()
        elif isinstance(entry, dict):
            name = None
            for key in ("name", "datastore", "datastoreName", "pvoName", "id"):
                if isinstance(entry.get(key), str):
                    name = entry[key].strip()
                    break
        else:
            name = None
        if name:
            names.append(name)

    return names


def write_output(names: list[str], base_url: str, output_file: str) -> None:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    separator = "=" * 72
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"{separator}\n")
        f.write(f"  Oracle Fusion BICC - Available Datastores\n")
        f.write(f"  Instance : {base_url}\n")
        f.write(f"  Generated: {generated}\n")
        f.write(f"{separator}\n\n")
        f.write(f"SUMMARY\n")
        f.write(f"{'-' * 40}\n")
        f.write(f"  Total datastores: {len(names)}\n\n")
        f.write(f"DATASTORES\n")
        f.write(f"{'-' * 72}\n")
        f.write(f"  {'#':<5} {'Datastore Name'}\n")
        f.write(f"  {'-' * 5} {'-' * 60}\n")
        for i, name in enumerate(names, start=1):
            f.write(f"  {i:<5} {name}\n")


def main() -> None:
    base_url  = _env("ORACLE_BASE_URL")
    username  = _env("ORACLE_USERNAME")
    password  = _env("ORACLE_PASSWORD")
    output_file = _env("OUTPUT_FILE", required=False) or DEFAULT_OUTPUT_FILE

    names = fetch_datastores(base_url, username, password)
    print(f"Received {len(names)} datastores.")

    write_output(names, base_url, output_file)
    print(f"Written to: {output_file}")


if __name__ == "__main__":
    main()

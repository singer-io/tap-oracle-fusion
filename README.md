# tap-oracle-fusion

Dynamic Singer tap for Oracle Fusion REST APIs.

## Features

- Dynamic stream discovery from Oracle resource metadata
- Dynamic schema and Singer metadata generation
- Optional sample-based type enrichment for schema generation
- Incremental sync when replication key is detected
- Full table sync fallback when no replication key is available

## Config

Example config is available in [config.json](config.json).

Required keys:

- start_date
- base_url or server/region/instance
- username/password or access_token

Important optional keys:

- api_families: list, default ["hcm", "fscm"]
- api_version: default "11.13.18.05"
- page_size: number of records to fetch per page (default: 100)

## Usage

Discover catalog:

```bash
tap-oracle-fusion --config config.json --discover > catalog.json
```

Sync data:

```bash
tap-oracle-fusion --config config.json --catalog catalog.json --state state.json
```

## API calls used by discovery

Per family/version:

- GET /{family}RestApi/resources/{version}

Per resource:

- GET /{family}RestApi/resources/{version}/{resource}/describe
- Optional sample call for schema enrichment:
	GET /{family}RestApi/resources/{version}/{resource}?limit={n}&offset=0

## API calls used by sync

Per selected stream:

- Resolve stream-to-resource path from current discovery config
- Paginated GET requests with limit/offset and next link handling
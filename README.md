# tap-oracle-fusion

Dynamic Singer tap for Oracle Fusion BICC datastores.

## Features

- Dynamic stream discovery from BICC datastore metadata
- Snake-case stream normalization for discovered datastores
- Dynamic schema and Singer metadata generation
- Discovery supports string-only datastore payloads and structured datastore payloads

## Config

Example config is available in [config.json](config.json).

Required keys:

- start_date
- base_url or server/region/instance
- username/password or access_token

Important optional keys:

- datastores (or streams/resources): list of datastore names to include during discovery
- discovery_parents: list of top-level datastore parents to include during discovery (for example: `FscmTopModelAM`, `CrmAnalyticsAM`). If set with `datastores`, both filters are applied.
- discovery_limit: integer cap for number of datastores to process during discovery (useful for validation runs)
- discovery_workers (or discovery_threads): number of concurrent workers for datastore detail discovery (`auto` or integer, default: auto, max: 128)
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

- GET /biacm/rest/meta/datastores
- GET /biacm/rest/meta/datastores/{datastoreName} (for column metadata)
- Each discovered stream stores its datastore path in stream metadata (`oracle-path`)

## API calls used by sync

Per selected stream:

- Resolve stream-to-datastore path from current discovery config
- Paginated GET requests with limit/offset and next link handling
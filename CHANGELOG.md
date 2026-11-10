# Changelog

## 0.0.4
  * Add optional `max_concurrent_streams` (default 1, max 4) to overlap BICC job creation, ESS submit/poll and manifest lookup across streams; record emission and state stay single-threaded.
  * Retry BICC SOAP calls on HTTP 429/503, honoring `Retry-After` (capped at 60 seconds).

## 0.0.3
  * Preserve distinct BICC rows that share a declared primary key.
  * Fail sync on BICC extraction errors instead of silently skipping streams.

## 0.0.2
  * Fixed BICC extraction to read all files from each run instead of only the last file, preventing missing records in multi-file extracts.

## 0.0.1
  * Initial Commit

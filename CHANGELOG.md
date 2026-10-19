# Changelog

## 0.0.4
  * Fixed an SSRF vulnerability. [#12](https://github.com/singer-io/tap-oracle-fusion/pull/12)

## 0.0.3
  * Preserve distinct BICC rows that share a declared primary key.
  * Fail sync on BICC extraction errors instead of silently skipping streams.

## 0.0.2
  * Fixed BICC extraction to read all files from each run instead of only the last file, preventing missing records in multi-file extracts.

## 0.0.1
  * Initial Commit

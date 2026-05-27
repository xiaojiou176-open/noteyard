# Test Data

This directory contains **minimal synthetic SQLite fixtures** used by tests.

The files in this directory are intentionally small schema fixtures for parser
and schema-detection coverage. They are not copied from a live Apple Notes
account and they are not intended to represent real user content.

- `icloud_min.sqlite`: minimal iCloud-style schema fixture for schema detection tests
- `legacy_min.sqlite`: minimal legacy schema fixture for schema detection tests

These fixtures are test artifacts for repository verification, not forensic
evidence samples.

Provenance-lite boundary:

- they were prepared as repository-local synthetic fixtures
- they are not exported from a live Apple Notes account
- they are not customer data, incident evidence, or production snapshots
- they should be treated as verification inputs, not showcase evidence bundles

# Changelog

All notable changes to `auraone-sdk` are documented here. This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-05-11

### Fixed

- Packaging: the 0.1.0 wheel only included the top-level `aura` and `aura_one` packages because `[tool.setuptools].packages` was an explicit list. Subpackages `aura_one.services`, `aura.operators`, and `aura.plugins` were missing, breaking `from aura_one import ...` on a fresh install. 0.1.1 switches to `setuptools.packages.find` to include all subpackages.

## [0.1.0] - 2026-05-11

Initial public release of the AuraOne Python SDK.

### Added

- `aura.client.AuraClient` and `aura_one` package: API-key auth, retries with exponential backoff, idempotent evaluation creation, polling helpers.
- `aura` CLI: `list-templates`, `evaluate`, `quotas`, `system-health`, and more.
- Airflow operator (`aura.operators.airflow_aura`) for triggering AuraOne evals from Airflow DAGs.
- GraphQL client (`aura_one.graphql`) alongside REST.
- Optional extras: `async` (httpx[http2]) and `dev` (pytest + build).

### Notes

- Requires an AuraOne account and API key.
- For local, no-account evaluation tooling, see [`auraone-evalkit`](https://pypi.org/project/auraone-evalkit/) and [`auraoneai/open`](https://github.com/auraoneai/open).

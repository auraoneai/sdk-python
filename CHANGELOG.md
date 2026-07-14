# Changelog

All notable changes to `auraone-sdk` are documented here. This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-07-13

### Fixed

- Corrected the PyPI long description and release-proof section so the package
  page identifies the published SDK instead of retaining pre-publication
  `0.2.0` candidate language.
- Updated package, module, CLI, test, and release-preflight version surfaces for
  the metadata-only patch release.

## [0.2.0] - 2026-07-12

### Added

- Added stable `table`, `json`, and `jsonl` CLI output formats for hosted evaluation workflows.
- Added `NO_COLOR` and `--no-color` support, environment-based CLI configuration, actionable error messages, and documented exit codes.
- Added source and distribution release preflight checks plus post-publish PyPI verification.

### Changed

- Rebuilt the PyPI trusted-publishing workflow around separately verified immutable artifacts and a clean-install verification job.
- Updated the CLI's default API endpoint to the hosted AuraOne API while preserving `--base-url` and `AURAONE_BASE_URL` overrides.

## [0.1.2] - 2026-07-07

### Changed

- Reworked the README around install, quickstart, concrete API examples, compatibility notes, and public project links.
- Expanded PyPI package metadata with a developer-facing description, search keywords, classifiers, changelog, and security links.
- Pruned tests and local macOS metadata from source distributions.
- Added test and Twine validation gates before trusted PyPI publishing.

### Fixed

- Aligned public SDK version surfaces with the package version.
- Corrected the security policy scope for the Python SDK.

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

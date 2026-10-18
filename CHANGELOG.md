# Changelog

All notable changes to `auraone-sdk` are documented here. This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-18

Published to PyPI on 2026-10-18 from the AuraOne monorepo release commit
`9b9548c1993477b792f8000a93854a6313cfe450`. This repository mirrors that
package source: the `v1.0.0` tag carries the same files as `sdks/python` at
that commit.

### Breaking

- Requires Python 3.10 or newer (was 3.9).
- API keys must be platform-issued `ak_<8 hex>_<64 hex>` keys; `aura_live_*`,
  `aura_test_*`, and `aoc_*` keys are rejected.
- All requests target the deployed `/api/...` contract on
  `https://api.auraone.ai`; the bare `/v1/*` and `/graphql` paths used by
  0.x were removed.
- Removed the robotics service (`aura_one.services.robotics`).
- Organization is derived from the API key record server-side. A configured
  `organization_id` is sent as a `?orgId=` assertion (a mismatch returns 403),
  never as a trusted header. The `"test"` key and `"public"` org defaults are
  gone, including the CLI's `--org-id` default.
- `EvaluationsService.cancel` posts to `/api/v1/evaluations/{id}/cancel`;
  `EvaluationStatus` gained `PENDING`, `CANCELLED`, and an `UNKNOWN` fallback
  for future statuses.
- Auth refresh sends `{ refreshToken }`, matching the platform schema.
- Plugins and operators call `evaluate()` (not the removed `run_evaluation`).
- The `async` extra now installs `aiofiles` instead of `httpx[http2]`.

### Behavior change

- Errors now come from the nested error body. When a route answers
  `{"error": {"code", "message"}}`, the raised error's `message` and `code`
  are the route's values, for every service. HTTP errors also raise their
  typed class (`NotFoundError`, `ServerError`, ...) instead of a generic
  `AuraOneError("Request failed: ...")`. Code that caught only `AuraOneError`
  still works (the typed errors subclass it); code that parsed the message
  text or read the error dict from `message` must read `error.code`,
  `error.status_code`, and `error.details` instead.

### Added

- `aura_one.services.enterprise_intelligence` covers every route under
  `api/v1/enterprise-intelligence` (96 operations) through grouped clients:
  `workflows`, `runs`, `batches`, `deliveries`, `human_tasks`, `connectors`,
  `tool_bindings`, `context_sources`, `historical_sets`, `improvement`,
  `regression`, `operations`, `registry`, plus `get_settings`,
  `get_dashboard`, `get_run_output`, `get_run_inputs`, and
  `get_connector_receipt`. The sync and async services share one definition.
- `EnterpriseIntelligenceUnavailableError` for any `503`; `is_truncated(meta)`
  for capped lists.
- `GraphQLService` and `AsyncGraphQLService` with persisted queries
  (`GRAPHQL_PERSISTED_QUERIES`); `IntegrationsService` and
  `AsyncIntegrationsService` for the connector namespaces in
  `SUPPORTED_CONNECTOR_NAMESPACES`; a `VERSION` constant.
- An optional `federation` extra (`cryptography`, `tenseal`) for the
  federated-learning participant client in `aura.federation`.
- `HttpClient.delete(path, config, data=None)` sends an optional JSON body;
  `HttpClient.post(..., files=...)` sends multipart form data. Both apply to
  `AsyncHttpClient`.

### Notes

- `tests/test_auth_format.py` and `tests/test_evaluations_contract.py` read
  shared fixtures from the AuraOne monorepo (`sdks/fixtures/` and
  `sdks/contract-fixtures/`), which are not part of this repository, so they
  do not run standalone here.
- This release was built and uploaded from the monorepo, not by this
  repository's `release-python.yml` workflow. It has no PyPI attestation and
  no GitHub Release assets.

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

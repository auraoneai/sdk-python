# AuraOne Python SDK

Run and automate hosted AuraOne evaluations from Python or the command line without rebuilding authentication, retry, service-client, and output plumbing.

[![PyPI version](https://img.shields.io/pypi/v/auraone-sdk.svg)](https://pypi.org/project/auraone-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/auraone-sdk.svg)](https://pypi.org/project/auraone-sdk/)
[![CI](https://github.com/auraoneai/sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/auraoneai/sdk-python/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/auraone-sdk.svg)](https://github.com/auraoneai/sdk-python/blob/main/LICENSE)

[PyPI](https://pypi.org/project/auraone-sdk/) |
[Source](https://github.com/auraoneai/sdk-python) |
[Releases](https://github.com/auraoneai/sdk-python/releases) |
[Documentation](https://www.auraone.ai/resources/docs) |
[TypeScript / Node.js: `@auraone/sdk`](https://www.npmjs.com/package/@auraone/sdk) |
[Local evaluation tools: `auraone-evalkit`](https://pypi.org/project/auraone-evalkit/)

`auraone-sdk` is the hosted-API client for Python developers, ML and platform engineers, notebook users, and CI maintainers who need to discover AuraOne templates, create evaluation runs, inspect results and quotas, or call related analytics, training, governance, robotics, labs, billing, integration, and GraphQL services.

The main differentiator is one distribution with three supported entry points: the synchronous `AuraOneClient`, the asynchronous `AsyncAuraOneClient`, and the `aura` CLI. All target the same configurable AuraOne API boundary; the package does not run evaluations locally.

## Choose This Package When

| Need | Use |
| --- | --- |
| Call hosted AuraOne evaluations from a Python service, worker, notebook, or CI job | `auraone-sdk` |
| Use `asyncio` while keeping the same service layout as the sync client | `AsyncAuraOneClient` from this package |
| Discover templates, create a run, or inspect quotas from shell automation | The bundled `aura` CLI |
| Validate rubrics or score saved outputs locally without an AuraOne account | [`auraone-evalkit`](https://pypi.org/project/auraone-evalkit/) |
| Integrate Node.js or TypeScript | [`@auraone/sdk`](https://www.npmjs.com/package/@auraone/sdk) and its [GitHub source](https://github.com/auraoneai/sdk-typescript) |
| Call an unsupported endpoint or fully control transport behavior | Direct `httpx` calls may be a better fit |

## Install

The distribution name is `auraone-sdk`, the primary import package is `aura_one`, and the console command is `aura`.

```bash
python -m pip install --upgrade auraone-sdk
python -c "import aura_one; print(aura_one.__version__)"
aura --version
```

The base installation includes the sync client, async client, and CLI. The `async` extra adds `httpx` HTTP/2 dependencies; it is not required for basic `AsyncAuraOneClient` use. The `dev` extra is for contributors and release validation.

```bash
python -m pip install "auraone-sdk[async]"
python -m pip install "auraone-sdk[dev]"
```

Package metadata requires Python 3.9 or newer. CI currently tests Python 3.9, 3.10, 3.11, and 3.12; newer Python versions are not yet part of the repository test matrix.

To work from source:

```bash
git clone https://github.com/auraoneai/sdk-python.git
cd sdk-python
python -m pip install -e ".[dev]"
```

## First Useful Workflow

Set an AuraOne API key in your shell or secret manager. Replace the example value; do not commit credentials.

```bash
export AURAONE_API_KEY="aura_live_00000000000000000000000000000000"
```

Start by discovering templates available to the authenticated account:

```python
from aura_one import AuraOneClient

with AuraOneClient.from_environment() as client:
    templates = client.evaluations.list_templates(per_page=5)

for template in templates:
    print(f"{template['id']}: {template.get('name', 'unnamed')}")
```

When you have a template ID and an agent bundle URL accepted by your AuraOne deployment, create a hosted evaluation:

```python
from aura_one import AuraOneClient

with AuraOneClient.from_environment() as client:
    evaluation = client.evaluations.create(
        template_id="cartpole-v1",
        agent_bundle_url="https://example.com/agent.zip",
        config={"seed": 42},
    )

print(
    {
        "id": evaluation["id"],
        "status": evaluation.get("status") or evaluation.get("state"),
    }
)
```

`evaluations.create()` returns the API JSON object. Store its `id`, then call `client.evaluations.get(evaluation_id)` from your worker or polling loop to inspect later state.

## Sync, Async, And CLI

### Synchronous Client

Use `AuraOneClient` in regular applications, scripts, notebooks, and synchronous workers. It exposes named services and closes its `httpx.Client` when used as a context manager.

```python
from aura_one import AuraOneClient

with AuraOneClient.with_api_key(
    "aura_live_00000000000000000000000000000000",
    base_url="https://api.auraone.ai",
    timeout=60.0,
    max_retries=3,
) as client:
    status = client.evaluations.get("eval_123")
```

Available service attributes are `auth`, `analytics`, `training`, `billing`, `collaboration`, `robotics`, `evaluations`, `labs`, `governance`, `integrations`, and `graphql`.

### Asynchronous Client

`AsyncAuraOneClient` mirrors the sync service layout and uses `httpx.AsyncClient`.

```python
import asyncio

from aura_one import AsyncAuraOneClient


async def main() -> None:
    async with AsyncAuraOneClient.from_environment() as client:
        templates = await client.evaluations.list_templates(
            domain="robotics",
            per_page=5,
        )
        print([template["id"] for template in templates])


asyncio.run(main())
```

### Command Line

The CLI covers the common hosted workflow: `list-templates`, `evaluate`, `quotas`, and `system-health`.

```bash
aura --help
aura list-templates
aura evaluate \
  --template-id cartpole-v1 \
  --agent-bundle-url https://example.com/agent.zip \
  --wait
aura quotas
aura system-health
```

The structured output and stable exit-code examples below describe the current `0.2.0` source candidate. Check `aura --version` and the [PyPI release page](https://pypi.org/project/auraone-sdk/) before depending on a flag in an installed release.

```bash
aura list-templates --domain robotics --output json
aura list-templates --output jsonl
NO_COLOR=1 aura system-health
```

### Compatibility Client

The `aura` import package also exposes `AuraClient`, the smaller compatibility client used by the CLI. New application integrations should normally start with `aura_one.AuraOneClient` or `aura_one.AsyncAuraOneClient`.

```python
from aura import AuraClient

client = AuraClient(
    api_key="aura_live_00000000000000000000000000000000",
    base_url="https://api.auraone.ai",
    org_id="public",
)
```

## Credentials, Endpoint, And Data Boundary

| Surface | Credentials | Base URL |
| --- | --- | --- |
| `AuraOneClient.from_environment()` and `AsyncAuraOneClient.from_environment()` | `AURAONE_API_KEY`, or `AURAONE_TOKEN` with optional `AURAONE_REFRESH_TOKEN` | Defaults to `https://api.auraone.ai`; pass `base_url=` explicitly to override |
| `AuraOneClient.with_api_key()` / `.with_token()` and async equivalents | Explicit API key or JWT | Defaults to `https://api.auraone.ai`; pass `base_url=` explicitly to override |
| `aura` CLI | `--api-key`, then `AURAONE_API_KEY` or `AURAONE_TOKEN` | `--base-url`, then `AURAONE_BASE_URL`, then `https://api.auraone.ai` |
| Compatibility `AuraClient` | Constructor `api_key` | Constructor `base_url`; `org_id` defaults to `public` |

The primary sync and async clients send API keys in `X-API-Key` and JWTs in `Authorization: Bearer ...`. The CLI compatibility client sends its credential as a bearer token and adds `X-Org-Id`.

The Python clients do **not** automatically read `AURAONE_BASE_URL`; only the CLI does. Pass the endpoint explicitly when using a private, staging, or self-hosted-compatible deployment:

```python
import os

from aura_one import AuraOneClient

client = AuraOneClient.from_environment(
    base_url=os.environ["AURAONE_BASE_URL"],
)
```

Data crossing the boundary is determined by the method you call:

- Every live operation sends an HTTP request to the configured base URL.
- Evaluation creation sends `template_id`, `agent_bundle_url`, and optional `reward_spec_id` and `config` values. The SDK sends the URL string; it does not read or upload a local bundle file.
- Analytics, training, governance, GraphQL, and other service calls send their method-specific parameters or JSON payloads.
- API responses are parsed and returned to the calling process. This package does not implement a local evaluation engine or a local results database.
- Credentials are retained in the client object for request headers; the SDK and CLI do not create a credential file.
- A custom base URL receives the configured credential and request data. Do not point an authenticated client at an endpoint you do not trust.
- `debug=True` can print request URLs and request bodies. Keep it disabled in logs that may contain sensitive payload data.

## Errors And Output Contracts

### Python

HTTP failures are normalized under `AuraOneError`. Common subclasses include `AuthenticationError`, `AuthorizationError`, `ValidationError`, `NotFoundError`, `ConflictError`, `RateLimitError`, `ServerError`, `NetworkError`, `TimeoutError`, and `ResponseParsingError`. GraphQL response errors raise `GraphQLExecutionError`.

```python
from aura_one import AuraOneError, AuthenticationError, RateLimitError

try:
    result = client.evaluations.get("eval_123")
except AuthenticationError as exc:
    raise RuntimeError("AuraOne rejected the configured credential") from exc
except RateLimitError as exc:
    print({"retry_after": exc.retry_after, "details": exc.details})
    raise
except AuraOneError as exc:
    print(
        {
            "message": exc.message,
            "code": exc.code,
            "status_code": exc.status_code,
            "details": exc.details,
        }
    )
    raise
```

Return types vary by service rather than being forced into one wrapper:

- Evaluation methods return API dictionaries or lists of dictionaries.
- GraphQL `execute()` returns the response `data` dictionary.
- Selected analytics helpers map JSON into exported dataclasses; many other service helpers return dictionaries, lists, or endpoint-specific text.
- The shared HTTP layer returns parsed JSON, `str` for text responses, or `bytes` for binary responses.

Treat the documented fields for the endpoint you call as the contract. Do not assume every service method returns the same object shape.

### CLI

For the current `0.2.0` source candidate:

- `table` is the interactive default.
- `json` writes one JSON document to stdout.
- `jsonl` writes one compact JSON object per record to stdout.
- Diagnostics and errors go to stderr.
- `NO_COLOR` or `--no-color` disables ANSI styling.

Machine-readable errors use this stderr shape:

```json
{"error":{"exit_code":3,"hint":"Set AURAONE_API_KEY or pass --api-key with a valid AuraOne API key.","message":"Authentication failed | Code: AUTH_ERROR | Status: 401","status_code":401,"type":"authentication_error"}}
```

| Exit code | Meaning |
| ---: | --- |
| `0` | Command completed successfully |
| `1` | Unexpected local failure |
| `2` | Invalid CLI usage or argument value |
| `3` | Authentication failed |
| `4` | Credential lacks permission |
| `5` | Resource was not found |
| `6` | Resource state conflict |
| `7` | Request validation failed |
| `8` | API rate limit reached |
| `9` | Network connection or timeout failure |
| `10` | AuraOne API or server failure |
| `130` | Command interrupted by the user |

## Source And Release Proof

Publication status checked on **July 13, 2026**:

| Surface | Version | Proof |
| --- | --- | --- |
| Published Python distribution | `0.1.2` | [PyPI release and files](https://pypi.org/project/auraone-sdk/0.1.2/#files), uploaded July 8, 2026 |
| Public source tag | `v0.1.2` | [GitHub tagged source](https://github.com/auraoneai/sdk-python/tree/v0.1.2) |
| Current repository source | `0.2.0` | `pyproject.toml`, `aura_one/version.py`, and `CHANGELOG.md` in this checkout |

`0.2.0` was not published on July 13, 2026. At that check date, PyPI had no `auraone-sdk==0.2.0` release and the public repository had no `v0.2.0` tag. A version present in source is release-candidate evidence, not registry availability. Use the linked PyPI page for current registry status.

Maintainers can reproduce the source and distribution checks without publishing:

```bash
version="$(python -c 'import aura_one; print(aura_one.__version__)')"
python scripts/release_preflight.py --expected-version "$version"
python -m pytest -q tests
python -m build
python -m twine check --strict dist/*
python scripts/release_preflight.py --expected-version "$version" --dist dist
```

The current [release workflow](https://github.com/auraoneai/sdk-python/blob/main/.github/workflows/release-python.yml) validates an existing signed version tag, matching source versions and changelog, tests the package, builds one wheel and one sdist, verifies a clean wheel install, and records SHA-256 checksums. Tag pushes and manual runs with `publish=false` are build-only. PyPI publication requires an explicit manual run with `publish=true`, the `pypi` environment, trusted-publishing OIDC, and the repository's coordinated publication authorization. Any reviewer gate comes from the protection rules configured on that GitHub environment. The post-publish jobs verify PyPI files and a clean registry install before creating or updating the matching GitHub Release.

## Limitations

- Live calls require access to an AuraOne API deployment and a credential accepted by that deployment.
- This package orchestrates hosted APIs; it does not execute evaluations, judges, rubric scoring, or report generation locally. Use [`auraone-evalkit`](https://pypi.org/project/auraone-evalkit/) for local, no-account evaluation utilities.
- Python 3.9 through 3.12 are the currently tested versions. Metadata allows newer Python 3 releases, but they are not yet claimed as tested.
- The package does not ship a `py.typed` marker, so type checkers should not treat it as a fully typed distribution.
- `AURAONE_REFRESH_TOKEN` can be loaded with a JWT, but the current HTTP clients do not implement an automatic token-refresh exchange.
- Airflow, Prefect, LangChain, and LlamaIndex helper modules expect a project-provided object or callback with `run_evaluation`; they are adapter hooks, not standalone hosted integrations.
- Named services cover the endpoints implemented in this repository, not every possible private or future API route.
- Browser and Node.js runtimes are outside this package. Use [`@auraone/sdk`](https://www.npmjs.com/package/@auraone/sdk) for Node.js and TypeScript.

## Project Links

- [Developer portal](https://www.auraone.ai/developers)
- [Documentation](https://www.auraone.ai/resources/docs)
- [PyPI package](https://pypi.org/project/auraone-sdk/)
- [GitHub source](https://github.com/auraoneai/sdk-python)
- [Issue tracker](https://github.com/auraoneai/sdk-python/issues)
- [Changelog](https://github.com/auraoneai/sdk-python/blob/main/CHANGELOG.md)
- [Security policy](https://github.com/auraoneai/sdk-python/blob/main/SECURITY.md)
- [Contributing guide](https://github.com/auraoneai/sdk-python/blob/main/CONTRIBUTING.md)
- [Code of conduct](https://github.com/auraoneai/sdk-python/blob/main/CODE_OF_CONDUCT.md)

## License

[MIT](https://github.com/auraoneai/sdk-python/blob/main/LICENSE)

## Next Action

Confirm the installed version, set a credential, and run template discovery against the intended endpoint:

```bash
python -m pip install --upgrade auraone-sdk
export AURAONE_API_KEY="aura_live_00000000000000000000000000000000"
aura --version
aura \
  --base-url https://api.auraone.ai \
  --api-key "$AURAONE_API_KEY" \
  list-templates
```

Then run `aura --help` for the exact CLI surface in that installed release, or use the sync quickstart above from application code.

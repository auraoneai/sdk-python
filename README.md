# AuraOne Python SDK

Use AuraOne's hosted evaluation, analytics, training, and governance APIs from Python code or the `aura` command line.

[![PyPI version](https://img.shields.io/pypi/v/auraone-sdk.svg)](https://pypi.org/project/auraone-sdk/)
[![PyPI downloads](https://img.shields.io/pypi/dm/auraone-sdk.svg)](https://pypi.org/project/auraone-sdk/)
[![license](https://img.shields.io/pypi/l/auraone-sdk.svg)](./LICENSE)
[![ci](https://github.com/auraoneai/sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/auraoneai/sdk-python/actions/workflows/ci.yml)

- Start AuraOne evaluations from Python services, notebooks, or CI jobs.
- List templates, create evaluations, poll results, cancel runs, and inspect quotas without hand-writing HTTP calls.
- Call advanced AuraOne surfaces for analytics, training export, robotics, labs, governance, integrations, GraphQL, and billing.
- Ship the same workflows from scripts or terminals with the bundled `aura` CLI.

## Install

```bash
pip install auraone-sdk
```

Optional extras:

```bash
pip install "auraone-sdk[async]"
pip install "auraone-sdk[dev]"
```

## Quickstart

Set an AuraOne API key, then list the evaluation templates available to your organization. Replace the example value with your real key.

```bash
export AURAONE_API_KEY="aura_live_00000000000000000000000000000000"
```

```python
from aura_one import AuraOneClient

client = AuraOneClient.from_environment()

templates = client.evaluations.list_templates(per_page=5)
for template in templates:
    print(f"{template['id']}: {template.get('name', 'unnamed')}")
```

Create an evaluation when you have a template ID and an agent bundle URL:

```python
from aura_one import AuraOneClient

client = AuraOneClient.from_environment()

evaluation = client.evaluations.create(
    template_id="cartpole-v1",
    agent_bundle_url="https://example.com/agent.zip",
)

print(evaluation["id"])
```

The CLI exposes the same common workflow:

```bash
aura --help
aura --base-url https://api.auraone.ai --api-key "$AURAONE_API_KEY" list-templates
aura --base-url https://api.auraone.ai --api-key "$AURAONE_API_KEY" evaluate \
  --template-id cartpole-v1 \
  --agent-bundle-url https://example.com/agent.zip
```

## What You Can Build

- Evaluation gates that start AuraOne runs from release pipelines.
- Internal model-quality dashboards that combine AuraOne analytics and evaluation status.
- Training-data export jobs for DPO, PPO, SFT, SPAN, and trajectory workflows.
- Robotics and labs automation that calls AuraOne service endpoints from Python.
- Custom orchestration around hosted evaluation jobs.
- Lightweight CLI scripts for quotas, system health, templates, and evaluations.

## Why auraone-sdk?

- **Hosted API workflows without request plumbing.** Authentication, base URL handling, retries, and response parsing live in the SDK instead of every script.
- **Python and terminal entry points.** Use `AuraOneClient` in application code and the `aura` CLI in shell-based workflows.
- **Service-specific clients.** Reach evaluation, analytics, training, robotics, governance, integrations, labs, billing, and GraphQL APIs from one package.
- **Adapter hooks included.** Airflow, Prefect, LangChain, and LlamaIndex helper modules are packaged for projects that provide a `run_evaluation` adapter.

## Compared To Direct HTTP

| Need | `auraone-sdk` | Direct `httpx` or generated client |
| --- | --- | --- |
| Start common evaluation workflows | Built-in `evaluations.create`, `list_templates`, and CLI commands | You assemble URLs, headers, payloads, retries, and output formatting |
| Use several AuraOne API areas | One client exposes named services | You maintain separate request helpers or generated surfaces |
| Keep scripts short | CLI and Python helpers cover common operations | More boilerplate, but full control over every request |
| Maximum customization | Supports request config and direct service calls | Direct HTTP is better when you need unsupported endpoints or custom transport behavior |

## API Usage

### Environment-based client

```python
from aura_one import AuraOneClient

client = AuraOneClient.from_environment()
print(client.is_authenticated())
```

`from_environment()` reads `AURAONE_API_KEY` or `AURAONE_TOKEN` with optional `AURAONE_REFRESH_TOKEN`.

### Explicit API key

```python
from aura_one import AuraOneClient

client = AuraOneClient.with_api_key(
    "aura_live_00000000000000000000000000000000",
    base_url="https://api.auraone.ai",
    timeout=60.0,
)
```

### Evaluations

```python
templates = client.evaluations.list_templates(domain="robotics", per_page=10)

evaluation = client.evaluations.create(
    template_id="cartpole-v1",
    agent_bundle_url="https://example.com/agent.zip",
    config={"seed": 42},
)

status = client.evaluations.get(evaluation["id"])
```

### Analytics

```python
response = client.analytics.track_user(
    "evaluation_started",
    properties={"template_id": "cartpole-v1"},
    user_id="user_123",
)

print(response.success)
```

### Training export

```python
from aura_one import TrainingExportRequest, TrainingFormat

request = TrainingExportRequest(
    org_id="org_123",
    format=TrainingFormat.DPO,
    min_confidence=3,
)

data = client.training.export_training_data(request)
```

### GraphQL

```python
data = client.graphql.execute(
    """
    query {
      viewer {
        id
      }
    }
    """
)
```

### Async client

```python
from aura_one import AsyncAuraOneClient

client = AsyncAuraOneClient.from_environment()

templates = await client.evaluations.list_templates(per_page=5)
await client.close()
```

### Lightweight legacy client

The `aura` package exports `AuraClient`, a smaller compatibility client used by the CLI:

```python
from aura import AuraClient

client = AuraClient(api_key="test", base_url="https://api.auraone.ai", org_id="public")
result = client.evaluate(
    template_id="cartpole-v1",
    agent_bundle_url="https://example.com/agent.zip",
    wait=False,
)
print(result.id)
```

## Examples

This repository currently keeps examples in the README and test suite:

- [CLI commands](#quickstart)
- [Evaluation client usage](#evaluations)
- [Analytics tracking](#analytics)
- [GraphQL execution](#graphql)
- Adapter-oriented Airflow, Prefect, LangChain, and LlamaIndex helper modules under [`aura/`](https://github.com/auraoneai/sdk-python/tree/main/aura)

## Compatibility And Limitations

- Requires Python 3.9 or newer.
- Requires an AuraOne hosted API account and API key for live API calls.
- Uses `httpx` for HTTP transport.
- Airflow, Prefect, LangChain, and LlamaIndex helper modules expect a project-provided object or callback with `run_evaluation`; use the documented `AuraOneClient` and `AuraClient` APIs directly unless you already have that adapter.
- The package does not ship a `py.typed` marker yet, so type checkers should treat it as a regular Python library rather than a fully typed package.
- Browser and Node.js runtimes are not supported by this Python package.
- The release workflow publishes to PyPI through GitHub Actions trusted publishing when a `v*` tag is pushed.

## Project Links

- [Documentation](https://www.auraone.ai/resources/docs)
- [Developer portal](https://www.auraone.ai/developers)
- [Changelog](./CHANGELOG.md)
- [Security policy](./SECURITY.md)
- [Code of conduct](./CODE_OF_CONDUCT.md)

## Contributing

Bug reports, documentation fixes, CLI improvements, and service convenience methods are welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md) for local setup and pull request expectations.

## License

[MIT](./LICENSE)

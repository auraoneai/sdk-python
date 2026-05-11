# AuraOne Python SDK

Lightweight Python SDK and CLI for AuraOne APIs.

## Installation

```bash
pip install auraone-sdk

# Optional extras
pip install "auraone-sdk[async]"
pip install "auraone-sdk[dev]"
```

> For local development workflows, see `CONTRIBUTING.md` instead of using editable installs in production environments.

## CLI Usage

```
aura --base-url https://api.auraone.ai --org-id public --api-key test list-templates

aura --base-url https://api.auraone.ai evaluate \
  --template-id cartpole-v1 \
  --agent-bundle-url https://example.com/agent.zip \
  --wait --robust

aura --base-url https://api.auraone.ai quotas
aura --base-url https://api.auraone.ai system-health
```

## Client Usage

```python
from aura.client import AuraClient

client = AuraClient(api_key="test", base_url="https://api.auraone.ai", org_id="public")
templates = client.list_templates()
res = client.evaluate(template_id="cartpole-v1", agent_bundle_url="https://example.com/agent.zip", wait=False)
final = client.wait_for_completion(res.id, timeout_seconds=120)
```

## Features

- Retries/backoff on transient failures (HTTP 5xx/timeouts)
- Idempotent evaluation creation with `X-Idempotency-Key`
- Polling helpers to wait for terminal states
- Advanced endpoints: analytics, benchmarks, quotas, safety, admin

# AuraOne Python SDK

Python SDK for AuraOne AI evaluation workflows: typed sync and async clients and the `aura` CLI for the hosted AuraOne API.

[![PyPI](https://img.shields.io/pypi/v/auraone-sdk)](https://pypi.org/project/auraone-sdk/)
[![CI](https://github.com/auraoneai/sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/auraoneai/sdk-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/auraoneai/sdk-python/blob/main/LICENSE)

## Quick start
```bash
pip install auraone-sdk
export AURAONE_API_KEY="ak_..."   # platform-issued key; never hard-code it
```

```python
import os
from aura_one import AuraOneClient
from aura_one.types import ClientConfig
client = AuraOneClient(ClientConfig(api_key=os.environ["AURAONE_API_KEY"]))
templates = client.evaluations.list_templates()
```

## What it does

- Calls the hosted AuraOne API at `https://api.auraone.ai` with a
  platform-issued `ak_` API key.
- Lists evaluation templates and creates, polls, and cancels evaluations
  (`client.evaluations`).
- Ships an async client (`AsyncAuraOneClient`) with the same methods.
- Installs the `aura` CLI (`aura evaluate`, `aura list-templates`,
  `aura quotas`, `aura system-health`).
- Covers the Enterprise Intelligence routes (`client.enterprise_intelligence`).

## What it doesn't do

- It does not run evaluations locally; the work runs on the AuraOne platform.
- Launch-excluded surfaces (compute, GraphQL, robotics, synthetic research,
  rewards) are not part of this SDK.
- It does not pick the tenant: the organization is always derived from the
  API key server-side.

## Build on AuraOne

- [Python SDK](https://auraone.ai/open/sdk-python)
- [TypeScript SDK](https://auraone.ai/open/sdk-typescript)
- [Self-hosted GitHub App](https://auraone.ai/open/github-app)

## Installation

```bash
pip install auraone-sdk
pip install "auraone-sdk[async]"  # async client
pip install "auraone-sdk[dev]"    # test tooling
```

## Authentication

Requests authenticate with a platform-issued API key:

```
ak_<8 lowercase hex>_<64 lowercase hex>
```

Keep it in an environment variable — never hard-code it:

```python
import os
from aura_one import AuraOneClient
from aura_one.types import ClientConfig

client = AuraOneClient(
    ClientConfig(
        api_key=os.environ["AURAONE_API_KEY"],        # ak_...
        base_url="https://api.auraone.ai",
        # Optional org assertion — must equal the key's organization;
        # the tenant is always derived from the key server-side.
        organization_id=os.environ.get("AURAONE_ORG_ID"),
    )
)
```

## Evaluations

```python
# List templates
templates = client.evaluations.list_templates()

# Create an evaluation — config.inputs is required
evaluation = client.evaluations.create(
    template_id="tpl_your_template",
    agent_bundle_url="https://example.com/agent.tar.gz",
    config={"inputs": [{"prompt": "example", "expected": "answer"}]},
)

# Poll + cancel
detail = client.evaluations.get(evaluation["id"])
client.evaluations.cancel(evaluation["id"])
```

## CLI

```bash
export AURAONE_API_KEY="ak_..."
aura evaluate \
  --template-id tpl_your_template \
  --agent-bundle-url https://example.com/agent.tar.gz \
  --wait

aura list-templates
aura quotas
aura system-health
```

The `aura` CLI and `AuraClient` read `AURAONE_API_KEY` when no
`--api-key`/`api_key` argument is given. `AURA_API_KEY` still works as a
deprecated fallback and emits a warning; with neither set the client raises
`ValueError` and the CLI exits 2.

## Enterprise Intelligence

`client.enterprise_intelligence` sends recurring work to AuraOne and reads
back finished, reviewed output. Software does the repeatable steps;
qualified people review exceptions.

Scopes: reads need `enterprise-intelligence.read`, writes need
`enterprise-intelligence.write`, and cancellation needs
`enterprise-intelligence.cancel`.

The flat methods are the customer surface. The grouped clients
(`workflows`, `runs`, `batches`, `deliveries`, `human_tasks`, `connectors`,
`tool_bindings`, `context_sources`, `historical_sets`, `improvement`,
`regression`, `operations`, `registry`) cover every other route. Many of
those also check the role of the user who created the key. Each method's
docstring names the role it needs. Complex bodies are TypedDicts with the
wire field names (see `aura_one.services.enterprise_intelligence._types`).

```python
ei = client.enterprise_intelligence

# Start one unit of work. Keep the key: retrying with it returns the same run.
inputs = ei.get_run_inputs()["data"]
run = ei.create_run(
    workflow_version_id="wfv_claims_intake",
    input_content_id=inputs["contents"][0]["id"],
    environment_version=inputs["environments"][0]["environmentVersion"],
    idempotency_key="claims-2026-10-06-0001",
)
delivery = ei.get_run_delivery(run["data"]["id"])

# Resolve an exception: ask, never guess.
task = ei.human_tasks.list(status="PENDING")["data"][0]
ei.human_tasks.complete(
    task["id"],
    action="REQUEST_INFORMATION",
    output_content_id="content_reply",
    evidence={"note": "Capacity is blank. Needs supplier confirmation."},
    expected_lock_version=task["lockVersion"],
)

# Upload a weekly queue as one batch (multipart; files keep source order).
ei.batches.ingest(
    workflow_version_id="wfv_menu_update",
    contract={
        "schemaVersion": "auraone.enterprise-ingestion.v1",
        "allowedMediaTypes": ["text/csv", "image/jpeg"],
        "spreadsheetMode": "ROW_PER_ITEM",
        "governance": {
            "dataClassification": "CONFIDENTIAL",
            "trainingRights": "NO_TRAINING",
            "retentionUntil": None,
            "legalHold": False,
        },
    },
    sources=[
        {"sourceId": "sheet", "fileName": "menu.csv", "mediaType": "text/csv",
         "content": open("menu.csv", "rb").read()},
    ],
)
```

The async client (`AsyncAuraOneClient`) has the same methods; `await` each
call.

- Idempotency: every write sends an `idempotency-key` header. Pass
  `idempotency_key` to retry safely; otherwise a UUID4 is generated per
  call. Keys must be 8-255 characters.
- Lists return at most 100 records and have no cursor. `meta["total"]`
  counts every match; `meta["loaded"]` counts what was returned. Use
  `is_truncated(meta)` and narrow with `q` and `status`.
- Any `503` raises `EnterpriseIntelligenceUnavailableError` after the
  client's retries. Other errors carry the route's `code` and `message`.
- Behavior change: errors now come from the nested error body
  (`{"error": {"code", "message"}}`) for every service, and HTTP errors
  raise their typed class (`NotFoundError`, `ServerError`, ...) instead of
  a generic `AuraOneError("Request failed: ...")`. Read `error.code`,
  `error.status_code` and `error.details`, not the message text. See
  `CHANGELOG.md`.

```python
from aura_one.services.enterprise_intelligence import (
    EnterpriseIntelligenceUnavailableError,
)

try:
    ei.list_runs()
except EnterpriseIntelligenceUnavailableError as error:
    print("Not available yet:", error.code)
```

The legacy `aura.enterprise_intelligence` client covers the customer read
routes and run creation only.

## Notes

- All requests target `https://api.auraone.ai/api/...`; there is no separate
  `/v1` host.
- Cookieless `ak_` requests are CSRF-exempt; browser session requests remain
  CSRF-protected.
- Launch-excluded surfaces (compute, GraphQL, robotics, synthetic research,
  rewards) are not part of this SDK.

---

Move from a prototype to a production AuraOne integration. [Talk to AuraOne](https://auraone.ai/contact?from=open:python-sdk)

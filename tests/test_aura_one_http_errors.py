"""HTTP-layer tests for envelope errors, DELETE bodies and multipart uploads.

Uses ``httpx.MockTransport`` so the real ``HttpClient`` / ``AsyncHttpClient``
request path runs without a network.
"""

import asyncio
import json

import httpx
import pytest

from aura_one.exceptions import (
    AuthorizationError,
    NotFoundError,
    ServerError,
    ValidationError,
    create_error_from_response,
)
from aura_one.services.enterprise_intelligence import (
    AsyncEnterpriseIntelligenceService,
    EnterpriseIntelligenceService,
    EnterpriseIntelligenceUnavailableError,
)
from aura_one.utils import AsyncHttpClient, HttpClient

BASE = "https://ei.test"


def _sync_client(handler, retries=0):
    client = HttpClient(BASE, max_retries=retries)
    client.retry_config.backoff_factor = 0
    client.client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def _async_client(handler):
    client = AsyncHttpClient(BASE, max_retries=0)
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


def test_nested_envelope_sets_code_and_message():
    error = create_error_from_response(
        404, {"error": {"code": "NOT_FOUND", "message": "Workflow not found."}}
    )
    assert isinstance(error, NotFoundError)
    assert error.code == "NOT_FOUND"
    assert error.message == "Workflow not found."


def test_nested_envelope_extra_keys_become_details():
    error = create_error_from_response(
        400,
        {"error": {"code": "WORKFLOW_GRAPH_INVALID", "message": "bad", "issues": [{"path": "n"}]}},
    )
    assert isinstance(error, ValidationError)
    assert error.details == {"issues": [{"path": "n"}]}


def test_flat_error_bodies_are_unchanged():
    error = create_error_from_response(403, {"error": "Forbidden", "code": "X"})
    assert isinstance(error, AuthorizationError)
    assert (error.message, error.code) == ("Forbidden", "X")


def test_body_without_error_fields_is_kept_as_details():
    body = {"status": "UNAVAILABLE", "worker": {"status": "DOWN"}}
    error = create_error_from_response(503, body)
    assert isinstance(error, ServerError)
    assert error.details == body


def test_503_through_real_client_raises_unavailable():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            503,
            json={"error": {"code": "ENTERPRISE_COMPOSITION_UNAVAILABLE", "message": "unavailable"}},
        )

    ei = EnterpriseIntelligenceService(_sync_client(handler, retries=1))
    with pytest.raises(EnterpriseIntelligenceUnavailableError) as raised:
        ei.runs.list()
    assert raised.value.code == "ENTERPRISE_COMPOSITION_UNAVAILABLE"
    assert raised.value.message == "unavailable"
    # 503 is retried before the typed error is raised.
    assert len(seen) == 2


def test_delete_with_body_sends_json():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": {"revoked": True}})

    ei = EnterpriseIntelligenceService(_sync_client(handler))
    ei.workflows.revoke_approval_decision(
        "wf-1", "req-1", "auraone", evidence={"reason": "scope changed"},
        idempotency_key="revoke-key-01",
    )
    request = seen[0]
    assert request.method == "DELETE"
    assert request.url.path == "/api/v1/enterprise-intelligence/workflows/wf-1/approval-requests/req-1/auraone"
    assert json.loads(request.content) == {"evidence": {"reason": "scope changed"}}
    assert request.headers["idempotency-key"] == "revoke-key-01"


def test_delete_without_body_sends_none():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": {}})

    EnterpriseIntelligenceService(_sync_client(handler)).tool_bindings.disable("tb-1")
    assert seen[0].method == "DELETE"
    assert seen[0].content == b""


def test_multipart_ingest_through_real_client():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(202, json={"data": {"receiptId": "r1"}})

    contract = {
        "schemaVersion": "auraone.enterprise-ingestion.v1",
        "allowedMediaTypes": ["text/csv"],
        "spreadsheetMode": "ROW_PER_ITEM",
        "governance": {
            "dataClassification": "CONFIDENTIAL",
            "trainingRights": "NO_TRAINING",
            "retentionUntil": None,
            "legalHold": False,
        },
    }
    EnterpriseIntelligenceService(_sync_client(handler)).batches.ingest(
        workflow_version_id="wfv-1",
        contract=contract,
        sources=[{"sourceId": "s", "fileName": "menu.csv", "mediaType": "text/csv", "content": "item,price"}],
        idempotency_key="ingest-key-01",
    )
    request = seen[0]
    content_type = request.headers["content-type"]
    assert content_type.startswith("multipart/form-data; boundary=")
    assert int(request.headers["content-length"]) == len(request.content)
    body = request.content.decode()
    assert 'name="workflowVersionId"' in body and "wfv-1" in body
    assert 'name="file"; filename="menu.csv"' in body
    assert "item,price" in body


def test_async_client_delete_with_body_and_503():
    seen = []

    def handler(request):
        seen.append(request)
        if request.method == "DELETE":
            return httpx.Response(200, json={"data": {}})
        return httpx.Response(503, json={"status": "UNAVAILABLE"})

    ei = AsyncEnterpriseIntelligenceService(_async_client(handler))

    async def run():
        await ei.workflows.revoke_approval_decision("w", "r", "customer", evidence={"x": 1})
        with pytest.raises(EnterpriseIntelligenceUnavailableError) as raised:
            await ei.get_health()
        return raised.value

    error = asyncio.run(run())
    assert json.loads(seen[0].content) == {"evidence": {"x": 1}}
    assert error.details == {"status": "UNAVAILABLE"}

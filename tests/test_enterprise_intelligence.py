"""Enterprise Intelligence service unit tests (mocked transport, no network).

Asserts each operation builds the documented method/path/headers/query and
parses the platform envelope. Mirrors the contract doc's EI table.
"""

import uuid

from aura.client import AuraClient
from aura.enterprise_intelligence import EnterpriseIntelligenceService

EI_BASE = "/api/v1/enterprise-intelligence"


class MockResponse:
    def __init__(self, status_code=200, json_data=None):
        self._status = status_code
        self._json = json_data or {}

    def raise_for_status(self):
        if self._status >= 400:
            raise Exception(f"HTTP {self._status}")

    def json(self):
        return self._json


class RecordingTransport:
    """Captures _request calls the way AuraClient issues them."""

    def __init__(self, response=None):
        self.calls = []
        self.response = response or MockResponse(200, {"data": {}})

    def request(self, method, url, json=None, params=None, headers=None):
        self.calls.append(
            {"method": method, "url": url, "json": json, "params": params, "headers": headers}
        )
        return self.response


def _client(response=None):
    client = AuraClient(api_key="ak_" + "0" * 8 + "_" + "f" * 64, base_url="http://localhost:9999")
    transport = RecordingTransport(response)
    client._client = transport  # type: ignore
    return client, transport


def test_service_is_exposed_on_client():
    client, _ = _client()
    ei = client.enterprise_intelligence
    assert isinstance(ei, EnterpriseIntelligenceService)
    # Lazy property caches the instance
    assert client.enterprise_intelligence is ei


def test_list_workflows_builds_queue_query():
    client, transport = _client(MockResponse(200, {"data": [], "meta": {"scope": "server"}}))
    out = client.enterprise_intelligence.list_workflows(q="kyc", status="ACTIVE")
    call = transport.calls[-1]
    assert call["method"] == "GET"
    assert call["url"] == f"http://localhost:9999{EI_BASE}/workflows"
    assert call["params"] == {"q": "kyc", "f.status": "ACTIVE"}
    assert out["data"] == []


def test_get_workflow_path():
    client, transport = _client(MockResponse(200, {"data": {"id": "wf-1"}}))
    out = client.enterprise_intelligence.get_workflow("wf-1")
    assert transport.calls[-1]["url"].endswith(f"{EI_BASE}/workflows/wf-1")
    assert out["data"]["id"] == "wf-1"


def test_list_runs_status_filter():
    client, transport = _client()
    client.enterprise_intelligence.list_runs(status="SUCCEEDED")
    call = transport.calls[-1]
    assert call["url"].endswith(f"{EI_BASE}/runs")
    assert call["params"] == {"f.status": "SUCCEEDED"}
    assert call["method"] == "GET"


def test_create_run_posts_strict_body_with_idempotency_key():
    client, transport = _client(
        MockResponse(202, {"data": {"id": "run-9"}, "links": {"self": f"{EI_BASE}/runs/run-9"}})
    )
    out = client.enterprise_intelligence.create_run(
        workflow_version_id="wfv-1",
        input_content_id="content-1",
        environment_version="env-1",
        deadline_at="2026-10-09T00:00:00Z",
        idempotency_key="contract-key-1234",
    )
    call = transport.calls[-1]
    assert call["method"] == "POST"
    assert call["url"].endswith(f"{EI_BASE}/runs")
    assert call["json"] == {
        "workflowVersionId": "wfv-1",
        "inputContentId": "content-1",
        "environmentVersion": "env-1",
        "deadlineAt": "2026-10-09T00:00:00Z",
    }
    assert call["headers"]["idempotency-key"] == "contract-key-1234"
    assert out["data"]["id"] == "run-9"


def test_create_run_autogenerates_valid_idempotency_key():
    client, transport = _client()
    client.enterprise_intelligence.create_run(
        workflow_version_id="wfv-1",
        input_content_id="content-1",
        environment_version="env-1",
    )
    key = transport.calls[-1]["headers"]["idempotency-key"]
    assert key and 8 <= len(key) <= 255
    uuid.UUID(key)


def test_run_reads_and_subresources():
    client, transport = _client()
    ei = client.enterprise_intelligence
    for method, suffix in [
        (ei.get_run, ""),
        (ei.get_run_output, "/output"),
        (ei.get_run_trace, "/trace"),
        (ei.get_run_delivery, "/delivery"),
    ]:
        method("run-1")
        assert transport.calls[-1]["url"].endswith(f"{EI_BASE}/runs/run-1{suffix}")
        assert transport.calls[-1]["method"] == "GET"


def test_get_run_inputs_search():
    client, transport = _client(MockResponse(200, {"data": {"contents": [], "environments": []}}))
    out = client.enterprise_intelligence.get_run_inputs(q="sha")
    call = transport.calls[-1]
    assert call["url"].endswith(f"{EI_BASE}/run-inputs")
    assert call["params"] == {"q": "sha"}
    assert out["data"] == {"contents": [], "environments": []}


def test_deliveries_paths():
    client, transport = _client()
    client.enterprise_intelligence.list_deliveries(status="AVAILABLE")
    call = transport.calls[-1]
    assert call["url"].endswith(f"{EI_BASE}/deliveries")
    assert call["params"] == {"f.status": "AVAILABLE"}
    client.enterprise_intelligence.get_delivery("del-1")
    assert transport.calls[-1]["url"].endswith(f"{EI_BASE}/deliveries/del-1")


def test_connector_receipts_paths_and_filters():
    client, transport = _client()
    client.enterprise_intelligence.list_connector_receipts("conn-1", run_id="run-1")
    call = transport.calls[-1]
    assert call["url"].endswith(f"{EI_BASE}/connectors/conn-1/receipts")
    assert call["params"] == {"runId": "run-1"}
    client.enterprise_intelligence.get_connector_receipt("conn-1", "rcpt-1", workflow_id="wf-1")
    call = transport.calls[-1]
    assert call["url"].endswith(f"{EI_BASE}/connectors/conn-1/receipts/rcpt-1")
    assert call["params"] == {"workflowId": "wf-1"}


def test_health_probe():
    client, transport = _client(
        MockResponse(200, {"status": "HEALTHY", "dependencies": {"database": {"status": "UP"}}})
    )
    out = client.enterprise_intelligence.get_health()
    assert transport.calls[-1]["url"].endswith(f"{EI_BASE}/health")
    assert out["status"] == "HEALTHY"

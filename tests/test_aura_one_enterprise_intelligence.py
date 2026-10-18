"""aura_one Enterprise Intelligence mutation contract tests (no network).

Each EI mutation route reads a required ``idempotency-key`` header (8-255 chars
after trimming) and parses a zod body. These tests pin the exact body keys and
header the aura_one service sends so they match the App Router routes.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from aura_one.services.enterprise_intelligence import (
    AsyncEnterpriseIntelligenceService,
    EnterpriseIntelligenceService,
)
from aura_one.types import RequestConfig

EI = "/api/v1/enterprise-intelligence"


class FakeHttp:
    def __init__(self):
        self.calls = []

    def post(self, path, data=None, config=None):
        self.calls.append(("POST", path, data, config))
        return {"data": {}}

    def get(self, path, params=None, config=None):
        self.calls.append(("GET", path, params, config))
        return {"data": {}}


class AsyncFakeHttp(FakeHttp):
    async def post(self, path, data=None, config=None):
        return FakeHttp.post(self, path, data, config)


def _key(config):
    assert isinstance(config, RequestConfig)
    key = config.headers["idempotency-key"]
    assert 8 <= len(key.strip()) <= 255
    return key


def test_create_run_sends_strict_body_and_generated_key():
    http = FakeHttp()
    EnterpriseIntelligenceService(http).create_run(
        workflow_version_id="wv_1",
        input_content_id="ic_1",
        environment_version="env-2026.10",
    )
    method, path, data, config = http.calls[0]
    assert (method, path) == ("POST", f"{EI}/runs")
    assert data == {
        "workflowVersionId": "wv_1",
        "inputContentId": "ic_1",
        "environmentVersion": "env-2026.10",
    }
    _key(config)


def test_create_run_deadline_and_supplied_key_verbatim():
    http = FakeHttp()
    deadline = datetime(2026, 10, 10, tzinfo=timezone.utc)
    EnterpriseIntelligenceService(http).create_run(
        workflow_version_id="wv_1",
        input_content_id="ic_1",
        environment_version="v1",
        deadline_at=deadline,
        idempotency_key="run-key-0001",
    )
    _, _, data, config = http.calls[0]
    assert data["deadlineAt"] == deadline.isoformat()
    assert set(data) == {"workflowVersionId", "inputContentId", "environmentVersion", "deadlineAt"}
    assert _key(config) == "run-key-0001"


def test_generated_keys_are_unique_per_call():
    http = FakeHttp()
    svc = EnterpriseIntelligenceService(http)
    for _ in range(2):
        svc.create_run(workflow_version_id="a", input_content_id="b", environment_version="c")
    assert _key(http.calls[0][3]) != _key(http.calls[1][3])


def test_caller_headers_preserved_and_config_not_mutated():
    http = FakeHttp()
    caller = RequestConfig(timeout=5, headers={"x-trace": "t1"})
    EnterpriseIntelligenceService(http).create_run(
        workflow_version_id="a",
        input_content_id="b",
        environment_version="c",
        request_config=caller,
    )
    config = http.calls[0][3]
    assert config.headers["x-trace"] == "t1"
    assert config.timeout == 5
    _key(config)
    assert caller.headers == {"x-trace": "t1"}


def test_caller_header_key_is_reused_when_no_argument():
    http = FakeHttp()
    EnterpriseIntelligenceService(http).create_run(
        workflow_version_id="a",
        input_content_id="b",
        environment_version="c",
        request_config=RequestConfig(headers={"Idempotency-Key": "header-key-1"}),
    )
    headers = http.calls[0][3].headers
    assert headers == {"idempotency-key": "header-key-1"}


@pytest.mark.parametrize("bad", ["short", "   seven  ", "x" * 256])
def test_invalid_supplied_key_rejected(bad):
    svc = EnterpriseIntelligenceService(FakeHttp())
    with pytest.raises(ValueError):
        svc.create_run(
            workflow_version_id="a",
            input_content_id="b",
            environment_version="c",
            idempotency_key=bad,
        )


def test_create_workflow_sends_key_and_name():
    http = FakeHttp()
    svc = EnterpriseIntelligenceService(http)
    svc.create_workflow(key="claims-intake", name="Claims intake", idempotency_key="wf-key-0001")
    svc.create_workflow(key="k2", name="N2", description="d")
    _, path, data, config = http.calls[0]
    assert path == f"{EI}/workflows"
    assert data == {"key": "claims-intake", "name": "Claims intake"}
    assert _key(config) == "wf-key-0001"
    assert http.calls[1][2] == {"key": "k2", "name": "N2", "description": "d"}
    _key(http.calls[1][3])


def test_complete_human_task_body():
    http = FakeHttp()
    EnterpriseIntelligenceService(http).complete_human_task(
        "task_1",
        action="APPROVE",
        output_content_id="oc_1",
        evidence={"note": "ok"},
        expected_lock_version=3,
    )
    _, path, data, config = http.calls[0]
    assert path == f"{EI}/human-tasks/task_1/complete"
    assert data == {
        "action": "APPROVE",
        "outputContentId": "oc_1",
        "evidence": {"note": "ok"},
        "expectedLockVersion": 3,
    }
    _key(config)


def test_complete_human_task_correction_and_null_evidence():
    http = FakeHttp()
    EnterpriseIntelligenceService(http).complete_human_task(
        "task_2",
        action="CORRECT",
        output_content_id="oc_2",
        evidence=None,
        expected_lock_version=0,
        correction={"field": "value"},
        idempotency_key="task-key-001",
    )
    _, _, data, config = http.calls[0]
    assert "evidence" in data and data["evidence"] is None
    assert data["correction"] == {"field": "value"}
    assert _key(config) == "task-key-001"


def test_run_regression_suite_body():
    http = FakeHttp()
    EnterpriseIntelligenceService(http).run_regression_suite(
        "suite_1", workflow_version_id="wv_1", evidence_id="ev_1"
    )
    _, path, data, config = http.calls[0]
    assert path == f"{EI}/regression-suites/suite_1/run"
    assert data == {"workflowVersionId": "wv_1", "evidenceId": "ev_1"}
    _key(config)


def test_async_create_run_body_and_key():
    http = AsyncFakeHttp()
    asyncio.run(
        AsyncEnterpriseIntelligenceService(http).create_run(
            workflow_version_id="wv_1",
            input_content_id="ic_1",
            environment_version="v1",
            idempotency_key="async-key-01",
        )
    )
    method, path, data, config = http.calls[0]
    assert (method, path) == ("POST", f"{EI}/runs")
    assert data == {"workflowVersionId": "wv_1", "inputContentId": "ic_1", "environmentVersion": "v1"}
    assert _key(config) == "async-key-01"

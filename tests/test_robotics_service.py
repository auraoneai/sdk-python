import asyncio
from typing import Any, Dict, List

import pytest

from aura_one.exceptions import AuraOneError, RateLimitError, ServerError
from aura_one.services.robotics import AsyncRoboticsService, RoboticsService
from aura_one.types import RequestConfig


class StubHttpClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def get(self, path: str, params=None, config=None):
        self.calls.append({"method": "GET", "path": path, "params": params, "config": config})

        page = int((params or {}).get("page", 1))
        if path == "/api/v1/robotics/datasets" and page == 1:
            return {
                "datasets": [{"id": "ds_1"}, {"id": "ds_2"}],
                "total": 3,
            }
        if path == "/api/v1/robotics/datasets" and page == 2:
            return {
                "datasets": [{"id": "ds_3"}],
                "total": 3,
            }
        return {}

    def post(self, path: str, data=None, config=None):
        self.calls.append({"method": "POST", "path": path, "data": data, "config": config})
        return {"ok": True, "path": path, "data": data}


class RetryHttpClient:
    def __init__(self) -> None:
        self.attempts = 0

    def post(self, path: str, data=None, config=None):
        self.attempts += 1
        if self.attempts == 1:
            raise ServerError("temporary")
        return {"status": "queued", "datasetId": data["datasetId"]}


class AsyncRetryHttpClient:
    def __init__(self) -> None:
        self.attempts = 0

    async def get(self, path: str, params=None, config=None):
        self.attempts += 1
        if self.attempts == 1:
            raise RateLimitError("slow down")
        return {
            "datasets": [{"id": "ds_1"}],
            "total": 1,
        }


def test_list_datasets_supports_pagination_filters() -> None:
    http = StubHttpClient()
    service = RoboticsService(http)

    result = service.list_datasets(page=2, limit=1, data_mode="HUMAN_DEMO")

    assert http.calls[0]["params"]["page"] == 2
    assert http.calls[0]["params"]["limit"] == 1
    assert http.calls[0]["params"]["dataMode"] == "HUMAN_DEMO"
    assert result["pagination"]["hasNext"] is True
    assert result["pagination"]["hasPrev"] is True


def test_iter_datasets_fetches_all_pages() -> None:
    http = StubHttpClient()
    service = RoboticsService(http)

    datasets = list(service.iter_datasets(limit=2))

    assert [dataset["id"] for dataset in datasets] == ["ds_1", "ds_2", "ds_3"]


def test_create_export_retries_retryable_errors() -> None:
    http = RetryHttpClient()
    service = RoboticsService(http)

    response = service.create_export(
        dataset_id="dataset_123",
        export_format="RLDS",
        config=RequestConfig(max_retries=1),
    )

    assert response["status"] == "queued"
    assert http.attempts == 2


def test_async_list_datasets_retries_rate_limit() -> None:
    http = AsyncRetryHttpClient()
    service = AsyncRoboticsService(http)

    response = asyncio.run(service.list_datasets(config=RequestConfig(max_retries=1)))

    assert response["datasets"][0]["id"] == "ds_1"
    assert http.attempts == 2


def test_workforce_methods_include_org_id() -> None:
    http = StubHttpClient()
    service = RoboticsService(http)

    service.list_workforce(org_id="org-123")
    service.assign_operator(
        org_id="org-123",
        operator_id="operator-1",
        task_type="teleoperation",
    )
    service.batch_assign(
        org_id="org-123",
        tasks=[{"taskType": "teleoperation", "priority": "normal", "slaMinutes": 60}],
    )

    list_call = http.calls[0]
    assign_call = http.calls[1]
    batch_call = http.calls[2]

    assert list_call["path"] == "/api/v1/robotics/workforce"
    assert list_call["params"]["orgId"] == "org-123"
    assert assign_call["data"]["orgId"] == "org-123"
    assert assign_call["data"]["action"] == "assign"
    assert batch_call["data"]["orgId"] == "org-123"
    assert batch_call["data"]["action"] == "batch_assign"


def test_workforce_methods_require_org_id() -> None:
    service = RoboticsService(StubHttpClient())

    with pytest.raises(AuraOneError, match="org_id is required"):
        service.list_workforce()

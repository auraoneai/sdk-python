from __future__ import annotations

import asyncio
import pytest

import aura
import aura_one
from aura.client import AuraClient
from aura.services.graphql import GraphQLService as AuraGraphQLService
from aura_one import AsyncAuraOneClient, AuraOneClient
from aura_one.services.graphql import (
    GRAPHQL_PERSISTED_QUERIES,
    AsyncGraphQLService,
    GraphQLExecutionError,
    GraphQLService,
)
from aura_one.types import ClientConfig, RequestConfig


VALID_KEY = "ak_" + "a1b2c3d4" + "_" + "0" * 64


class FakeHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, path, data=None, config: RequestConfig | None = None):
        self.calls.append({"path": path, "data": data, "config": config})
        return self.payload


class FakeAsyncHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def post(self, path, data=None, config: RequestConfig | None = None):
        self.calls.append({"path": path, "data": data, "config": config})
        return self.payload


def test_aura_and_aura_one_export_version_and_graphql_service():
    assert aura.VERSION == aura_one.VERSION
    assert aura.GraphQLService is AuraGraphQLService
    assert aura_one.GraphQLService is GraphQLService


def test_graphql_service_execute_and_query_target_api_graphql():
    http = FakeHttpClient({"data": {"jobs": [{"id": "job-1"}]}})
    service = GraphQLService(http)

    data = service.execute(
        "query OptimizationJobs($limit: Int) { jobs(limit: $limit) { id } }",
        variables={"limit": 5},
        operation_name="OptimizationJobs",
    )
    assert data == {"jobs": [{"id": "job-1"}]}
    assert http.calls[0]["path"] == "/api/graphql"
    assert http.calls[0]["data"] == {
        "query": "query OptimizationJobs($limit: Int) { jobs(limit: $limit) { id } }",
        "variables": {"limit": 5},
        "operationName": "OptimizationJobs",
    }


def test_graphql_service_persisted_optimization_job_query():
    http = FakeHttpClient({"data": {"job": {"id": "job-9", "status": "running"}}})
    service = GraphQLService(http)
    job = service.get_optimization_job("job-9")
    assert job == {"id": "job-9", "status": "running"}
    assert http.calls[0]["data"]["extensions"] == {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": GRAPHQL_PERSISTED_QUERIES["OptimizationJob"]["sha256Hash"],
        }
    }


def test_graphql_service_raises_on_errors():
    http = FakeHttpClient(
        {
            "errors": [
                {
                    "message": "PersistedQueryNotAllowed",
                    "extensions": {"code": "PERSISTED_QUERY_NOT_ALLOWED"},
                }
            ]
        }
    )
    service = GraphQLService(http)
    with pytest.raises(GraphQLExecutionError) as exc_info:
        service.execute("{ jobs { id } }")
    assert exc_info.value.code == "PERSISTED_QUERY_NOT_ALLOWED"


def test_async_graphql_service_execute():
    async def _run():
        http = FakeAsyncHttpClient({"data": {"job": {"id": "j-1"}}})
        service = AsyncGraphQLService(http)
        return await service.execute("query { job(id: \"j-1\") { id } }")

    data = asyncio.run(_run())
    assert data == {"job": {"id": "j-1"}}


def test_clients_wire_graphql_service():
    aura_client = AuraClient(api_key=VALID_KEY, org_id="org_1")
    sync_client = AuraOneClient(ClientConfig(api_key=VALID_KEY, organization_id="org_1"))
    async_client = AsyncAuraOneClient(
        ClientConfig(api_key=VALID_KEY, organization_id="org_1")
    )

    assert isinstance(aura_client.graphql, GraphQLService)
    assert isinstance(sync_client.graphql, GraphQLService)
    assert isinstance(async_client.graphql, AsyncGraphQLService)

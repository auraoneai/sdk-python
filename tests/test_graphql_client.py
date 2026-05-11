from __future__ import annotations

import asyncio
import pytest

from aura_one.graphql import GraphQLClient, AsyncGraphQLClient, GraphQLExecutionError
from aura_one.types import RequestConfig


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


def test_graphql_client_returns_data():
    client = GraphQLClient(FakeHttpClient({"data": {"hello": "world"}}))
    data = client.execute("query { hello }")
    assert data["hello"] == "world"


def test_graphql_client_raises_on_errors():
    client = GraphQLClient(FakeHttpClient({"errors": [{"message": "boom"}]}))
    with pytest.raises(GraphQLExecutionError):
        client.execute("query { boom }")


def test_async_graphql_client():
    async def _execute():
        client = AsyncGraphQLClient(FakeAsyncHttpClient({"data": {"ping": "pong"}}))
        return await client.execute("query { ping }")

    data = asyncio.run(_execute())
    assert data["ping"] == "pong"

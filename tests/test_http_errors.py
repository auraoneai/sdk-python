from __future__ import annotations

import asyncio

import httpx
import pytest

from aura_one.exceptions import AuthenticationError
from aura_one.utils import AsyncHttpClient, HttpClient


def test_sync_http_client_preserves_typed_http_errors() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            401,
            json={"error": "bad key", "code": "bad_key"},
            request=request,
        )
    )
    client = HttpClient(base_url="https://api.auraone.ai", max_retries=0)
    client.client = httpx.Client(transport=transport)

    with pytest.raises(AuthenticationError) as exc_info:
        client.get("/v1/templates")

    assert exc_info.value.message == "bad key"
    assert exc_info.value.code == "bad_key"


def test_async_http_client_preserves_typed_http_errors() -> None:
    async def execute() -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                401,
                json={"error": "bad key", "code": "bad_key"},
                request=request,
            )
        )
        client = AsyncHttpClient(base_url="https://api.auraone.ai", max_retries=0)
        client.client = httpx.AsyncClient(transport=transport)

        with pytest.raises(AuthenticationError) as exc_info:
            await client.get("/v1/templates")

        assert exc_info.value.message == "bad key"
        assert exc_info.value.code == "bad_key"

    asyncio.run(execute())

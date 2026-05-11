from aura_one import AuraOneClient, AsyncAuraOneClient
from aura_one.types import ClientConfig


def test_sync_client_exposes_public_service_surfaces():
    client = AuraOneClient(ClientConfig(api_key="test"))

    assert client.evaluations is not None
    assert client.labs is not None
    assert client.governance is not None
    assert client.integrations is not None


def test_async_client_exposes_public_service_surfaces():
    client = AsyncAuraOneClient(ClientConfig(api_key="test"))

    assert client.evaluations is not None
    assert client.labs is not None
    assert client.governance is not None
    assert client.integrations is not None

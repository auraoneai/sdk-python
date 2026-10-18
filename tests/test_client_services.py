from aura_one import AuraOneClient, AsyncAuraOneClient
from aura_one.types import ClientConfig

VALID_KEY = "ak_" + "0" * 8 + "_" + "f" * 64


def test_sync_client_exposes_public_service_surfaces():
    client = AuraOneClient(ClientConfig(api_key=VALID_KEY))

    assert client.evaluations is not None
    assert client.labs is not None
    assert client.governance is not None
    assert client.integrations is not None
    assert client.graphql is not None
    # Launch-excluded surfaces are not exposed (PR-19 T-P0-15).
    assert not hasattr(client, "robotics")
    assert not hasattr(client, "compute")


def test_async_client_exposes_public_service_surfaces():
    client = AsyncAuraOneClient(ClientConfig(api_key=VALID_KEY))

    assert client.evaluations is not None
    assert client.labs is not None
    assert client.governance is not None
    assert client.integrations is not None
    assert client.graphql is not None
    assert not hasattr(client, "robotics")
    assert not hasattr(client, "compute")


def test_sync_client_exposes_enterprise_intelligence_service():
    client = AuraOneClient(ClientConfig(api_key=VALID_KEY))
    assert client.enterprise_intelligence is not None
    for method in (
        "list_workflows",
        "get_workflow",
        "list_runs",
        "get_run",
        "create_run",
        "list_deliveries",
        "list_human_tasks",
        "list_connectors",
        "list_improvement_items",
        "list_evaluations",
        "list_regression_suites",
    ):
        assert callable(getattr(client.enterprise_intelligence, method))


def test_async_client_exposes_enterprise_intelligence_service():
    client = AsyncAuraOneClient(ClientConfig(api_key=VALID_KEY))
    assert client.enterprise_intelligence is not None
    for method in (
        "list_workflows",
        "list_runs",
        "list_deliveries",
        "list_human_tasks",
        "list_connectors",
        "list_improvement_items",
        "list_evaluations",
        "list_regression_suites",
    ):
        assert callable(getattr(client.enterprise_intelligence, method))

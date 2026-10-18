from __future__ import annotations

from aura.client import AuraClient
from aura.services.integrations import (
    SUPPORTED_CONNECTOR_NAMESPACES,
    IntegrationsService,
)
from aura_one import AuraOneClient
from aura_one.types import ClientConfig


VALID_KEY = "ak_" + "a1b2c3d4" + "_" + "0" * 64


class RecordingHttpClient:
    def __init__(self):
        self.calls = []

    def get(self, path, params=None, config=None):
        self.calls.append({"method": "GET", "path": path, "params": params})
        return {"success": True, "data": []}

    def post(self, path, data=None, config=None):
        self.calls.append({"method": "POST", "path": path, "data": data})
        return {"success": True, "data": {"ok": True}}


def test_all_16_plus_2_connectors_exposed_on_aura_and_aura_one():
    aura_client = AuraClient(api_key=VALID_KEY)
    aura_one_client = AuraOneClient(ClientConfig(api_key=VALID_KEY))

    assert list(SUPPORTED_CONNECTOR_NAMESPACES) == [
        "githubActions",
        "gitlabCi",
        "jenkins",
        "circleci",
        "snowflake",
        "bigquery",
        "databricks",
        "s3",
        "pagerduty",
        "opsgenie",
        "slack",
        "teams",
        "jira",
        "datadog",
        "grafana",
        "splunk",
        "salesforce",
        "hubspot",
    ]

    for namespace in SUPPORTED_CONNECTOR_NAMESPACES:
        assert hasattr(aura_client.integrations, namespace)
        assert hasattr(aura_one_client.integrations, namespace)


def test_connector_actions_dispatch_expected_payloads():
    http = RecordingHttpClient()
    integrations = IntegrationsService(http)

    integrations.githubActions.dispatch_workflow(
        owner="aura", repo="evals", workflow_id="ci.yml", ref="main"
    )
    integrations.gitlabCi.trigger_pipeline(project_id=123, ref="main")
    integrations.jenkins.trigger_job(job_name="regressions", parameters={"SHA": "abc"})
    integrations.circleci.trigger_pipeline(project_slug="gh/auraone/evals", branch="main")
    integrations.snowflake.provision_connection("prod-warehouse", {"account": "xy"})
    integrations.bigquery.start_sync(
        "conn-1", {"sourceTable": "runs", "targetDataset": "auraone"}
    )
    integrations.databricks.run_job(job_id=42, notebook_params={"runId": "r-1"})
    integrations.s3.store(
        b"payload",
        {"organizationId": "org_1", "key": "evidence.json", "dataClassification": "confidential"},
    )
    integrations.pagerduty.trigger_incident(
        summary="Eval failed", source="AuraOne", severity="critical"
    )
    integrations.opsgenie.create_alert(message="Regression bank stall", priority="P2")
    integrations.slack.send_interview_notification(
        {"type": "interview_completed", "channel": "#evals"}
    )
    integrations.teams.send_message(title="Run passed", text="All checks green")
    integrations.jira.create_issue(
        project_key="AURA", summary="Evaluation failure", description="details"
    )
    integrations.datadog.send_metric(name="eval.latency", value=120.0, metric_type="gauge")
    integrations.grafana.create_annotation(text="Regression gate tripped", time=1700000000000)
    integrations.splunk.send_events([{"event": "audit.completed"}])
    integrations.salesforce.upsert_record(object_name="Account", record={"Name": "Acme"})
    integrations.hubspot.upsert_contact(email="ops@example.com", firstname="Ada")

    assert len(http.calls) == 18
    assert http.calls[0] == {
        "method": "POST",
        "path": "/api/v1/integrations/connectors/github-actions",
        "data": {
            "action": "dispatchWorkflow",
            "payload": {
                "owner": "aura",
                "repo": "evals",
                "workflowId": "ci.yml",
                "ref": "main",
            },
            "operation": "invoke",
        },
    }
    assert http.calls[16]["path"] == "/api/v1/integrations/connectors/salesforce"
    assert http.calls[17]["path"] == "/api/v1/integrations/connectors/hubspot"


def test_connector_framework_connect_test_sync_route_shapes():
    """SDK hits the real connector framework endpoints with operation bodies."""
    http = RecordingHttpClient()
    integrations = IntegrationsService(http)

    integrations.pagerduty.connect({"routingKey": "pd-key-1"})
    integrations.pagerduty.test({"connectorId": "conn_1"})
    integrations.slack.sync({"table": "runs"})
    integrations.slack.invoke("postRunEvent", {"runId": "r-1", "summary": "ok"})

    assert http.calls[0] == {
        "method": "POST",
        "path": "/api/v1/integrations/connectors/pagerduty",
        "data": {
            "operation": "install",
            "credentials": {"routingKey": "pd-key-1"},
        },
    }
    assert http.calls[1] == {
        "method": "POST",
        "path": "/api/v1/integrations/connectors/pagerduty",
        "data": {"connectorId": "conn_1", "operation": "test"},
    }
    assert http.calls[2] == {
        "method": "POST",
        "path": "/api/v1/integrations/connectors/slack",
        "data": {
            "eventType": "sync.requested",
            "payload": {"table": "runs"},
            "operation": "dispatch",
        },
    }
    assert http.calls[3] == {
        "method": "POST",
        "path": "/api/v1/integrations/connectors/slack",
        "data": {
            "action": "postRunEvent",
            "payload": {"runId": "r-1", "summary": "ok"},
            "operation": "invoke",
        },
    }

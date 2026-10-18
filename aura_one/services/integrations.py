"""Integrations service and 16+2 connector namespaces for AuraOne SDK."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote

from ..types import RequestConfig
from ..utils import HttpClientProtocol


SUPPORTED_CONNECTOR_NAMESPACES = (
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
)


def _encode_segment(value: str) -> str:
    return quote(str(value), safe="")


def _normalize_binary(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(data)).decode("ascii")
    return str(data)


def _unwrap_response(resp: Any) -> Dict[str, Any]:
    if hasattr(resp, "raise_for_status") and callable(resp.raise_for_status):
        status_code = getattr(resp, "status_code", 200)
        if isinstance(status_code, int) and status_code >= 400:
            resp.raise_for_status()
    if hasattr(resp, "json") and callable(resp.json):
        return resp.json()
    if isinstance(resp, dict):
        return resp
    return {"data": resp}


def _http_get(
    http_client: Any,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    config: Optional[RequestConfig] = None,
) -> Dict[str, Any]:
    if hasattr(http_client, "_request") and callable(http_client._request):
        headers = config.headers if config and config.headers else None
        resp = http_client._request("GET", path, params=params, headers=headers)
        return _unwrap_response(resp)
    return http_client.get(path, params=params, config=config)


def _http_post(
    http_client: Any,
    path: str,
    data: Optional[Dict[str, Any]] = None,
    config: Optional[RequestConfig] = None,
) -> Dict[str, Any]:
    if hasattr(http_client, "_request") and callable(http_client._request):
        headers = config.headers if config and config.headers else None
        resp = http_client._request("POST", path, json=data, headers=headers)
        return _unwrap_response(resp)
    return http_client.post(path, data=data, config=config)


class BaseConnectorNamespace:
    """Base synchronous connector namespace."""

    def __init__(self, provider_id: str, http_client: Any) -> None:
        self.provider_id = provider_id
        self.http_client = http_client

    def connect(
        self,
        payload: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        # Connector framework install:
        # POST /api/v1/integrations/connectors/{provider} {"operation": "install"}
        merged = {**(payload or {}), **kwargs}
        credentials = merged.pop("credentials", None)
        extras: Dict[str, Any] = {}
        for key in ("config", "name", "environment", "subscribedEvents"):
            if key in merged:
                extras[key] = merged.pop(key)
        body: Dict[str, Any] = {"operation": "install"}
        body["credentials"] = (
            credentials if isinstance(credentials, dict) else merged
        )
        body.update(extras)
        path = f"/api/v1/integrations/connectors/{_encode_segment(self.provider_id)}"
        return _http_post(self.http_client, path, data=body, config=request_config)

    def test(
        self,
        payload: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        # Connector framework test:
        # POST /api/v1/integrations/connectors/{provider} {"operation": "test"}
        body = {**(payload or {}), **kwargs, "operation": "test"}
        path = f"/api/v1/integrations/connectors/{_encode_segment(self.provider_id)}"
        return _http_post(self.http_client, path, data=body, config=request_config)

    def sync(
        self,
        payload: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        # Connector framework durable dispatch queue:
        # POST /api/v1/integrations/connectors/{provider}
        #   {"operation": "dispatch", "eventType": ..., "payload": {...}}
        merged = {**(payload or {}), **kwargs}
        event_type = merged.pop("eventType", None) or merged.pop(
            "event_type", None
        )
        if not (isinstance(event_type, str) and event_type.strip()):
            event_type = "sync.requested"
        body = {
            "eventType": event_type,
            "payload": merged,
            "operation": "dispatch",
        }
        path = f"/api/v1/integrations/connectors/{_encode_segment(self.provider_id)}"
        return _http_post(self.http_client, path, data=body, config=request_config)

    def invoke(
        self,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        # Connector framework invoke:
        # POST /api/v1/integrations/connectors/{provider}
        #   {"operation": "invoke", "action": ..., "payload": {...}}
        # replaces the retired per-provider workflow execute surface.
        merged = {**(payload or {}), **kwargs}
        path = f"/api/v1/integrations/connectors/{_encode_segment(self.provider_id)}"
        return _http_post(
            self.http_client,
            path,
            data={
                "action": action,
                "payload": merged,
                "operation": "invoke",
            },
            config=request_config,
        )


class GitHubActionsConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("github-actions", http_client)

    def dispatch_workflow(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        workflow_id: Optional[str] = None,
        workflowId: Optional[str] = None,
        ref: str = "main",
        inputs: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        if owner is not None:
            body["owner"] = owner
        if repo is not None:
            body["repo"] = repo
        resolved_wf = workflowId or workflow_id or body.pop("workflow_id", None) or body.get("workflowId")
        if resolved_wf is not None:
            body["workflowId"] = resolved_wf
        body.setdefault("ref", ref)
        if inputs is not None:
            body["inputs"] = inputs
        return self.invoke("dispatchWorkflow", body, request_config=request_config)

    dispatchWorkflow = dispatch_workflow


class GitLabCIConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("gitlab-ci", http_client)

    def trigger_pipeline(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        project_id: Optional[Union[int, str]] = None,
        projectId: Optional[Union[int, str]] = None,
        ref: str = "main",
        variables: Optional[Dict[str, str]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        resolved_project = projectId if projectId is not None else (project_id if project_id is not None else body.pop("project_id", None))
        if resolved_project is not None:
            body["projectId"] = resolved_project
        body.setdefault("ref", ref)
        if variables is not None:
            body["variables"] = variables
        return self.invoke("triggerPipeline", body, request_config=request_config)

    triggerPipeline = trigger_pipeline


class JenkinsConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("jenkins", http_client)

    def trigger_job(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        job_name: Optional[str] = None,
        jobName: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        resolved_job = jobName or job_name or body.pop("job_name", None)
        if resolved_job is not None:
            body["jobName"] = resolved_job
        if parameters is not None:
            body["parameters"] = parameters
        return self.invoke("triggerJob", body, request_config=request_config)

    triggerJob = trigger_job


class CircleCIConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("circleci", http_client)

    def trigger_pipeline(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        project_slug: Optional[str] = None,
        projectSlug: Optional[str] = None,
        branch: Optional[str] = "main",
        tag: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        resolved_slug = projectSlug or project_slug or body.pop("project_slug", None)
        if resolved_slug is not None:
            body["projectSlug"] = resolved_slug
        if branch is not None and "branch" not in body:
            body["branch"] = branch
        if tag is not None:
            body["tag"] = tag
        if parameters is not None:
            body["parameters"] = parameters
        return self.invoke("triggerPipeline", body, request_config=request_config)

    triggerPipeline = trigger_pipeline


class SnowflakeConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("snowflake", http_client)

    def provision_connection(
        self,
        connection_name: Union[str, Dict[str, Any], None] = None,
        config: Optional[Dict[str, Any]] = None,
        *,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if isinstance(connection_name, dict):
            body = {**connection_name, **kwargs}
        else:
            body = {
                "connectionName": connection_name or kwargs.pop("connectionName", None),
                "config": config or kwargs.pop("config", {}) or {},
                **kwargs,
            }
        return self.invoke("provisionConnection", body, request_config=request_config)

    provisionConnection = provision_connection

    def execute_query(
        self,
        sql: Union[str, Dict[str, Any]],
        bindings: Optional[List[Any]] = None,
        *,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if isinstance(sql, dict):
            body = {**sql, **kwargs}
        else:
            body = {"sql": sql, **(({"bindings": bindings}) if bindings is not None else {}), **kwargs}
        return self.invoke("executeQuery", body, request_config=request_config)

    executeQuery = execute_query


class BigQueryConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("bigquery", http_client)

    def start_sync(
        self,
        connection_id: Union[str, Dict[str, Any], None] = None,
        options: Optional[Dict[str, Any]] = None,
        *,
        source_table: Optional[str] = None,
        target_dataset: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if isinstance(connection_id, dict):
            body = {**connection_id, **(options or {}), **kwargs}
        else:
            body = {
                "connectionId": connection_id or kwargs.pop("connectionId", None),
                **(options or {}),
                **kwargs,
            }
        if source_table is not None:
            body["sourceTable"] = source_table
        if target_dataset is not None:
            body["targetDataset"] = target_dataset
        return self.invoke("startSync", body, request_config=request_config)

    startSync = start_sync


class DatabricksConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("databricks", http_client)

    def run_job(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        job_id: Optional[Union[int, str]] = None,
        jobId: Optional[Union[int, str]] = None,
        notebook_params: Optional[Dict[str, Any]] = None,
        notebookParams: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        resolved_job = jobId if jobId is not None else (job_id if job_id is not None else body.pop("job_id", None))
        if resolved_job is not None:
            body["jobId"] = resolved_job
        resolved_params = notebookParams or notebook_params or body.pop("notebook_params", None)
        if resolved_params is not None:
            body["notebookParams"] = resolved_params
        return self.invoke("runJob", body, request_config=request_config)

    runJob = run_job


class S3Connector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("amazon-s3", http_client)

    def store(
        self,
        data: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        key: Optional[str] = None,
        organization_id: Optional[str] = None,
        organizationId: Optional[str] = None,
        data_classification: Optional[str] = None,
        dataClassification: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if isinstance(data, dict) and metadata is None and ("key" in data or "contentBase64" in data):
            body = {**data, **kwargs}
        else:
            body = {**(metadata or {}), **kwargs}
            if data is not None:
                body["contentBase64"] = _normalize_binary(data)
        if key is not None:
            body["key"] = key
        resolved_org = organizationId or organization_id or body.pop("organization_id", None)
        if resolved_org is not None:
            body["organizationId"] = resolved_org
        resolved_class = dataClassification or data_classification or body.pop("data_classification", None)
        if resolved_class is not None:
            body["dataClassification"] = resolved_class
        return self.invoke("store", body, request_config=request_config)


class PagerDutyConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("pagerduty", http_client)

    def trigger_incident(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        summary: Optional[str] = None,
        source: str = "AuraOne",
        severity: str = "critical",
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        if summary is not None:
            body["summary"] = summary
        body.setdefault("source", source)
        body.setdefault("severity", severity)
        return self.invoke("triggerIncident", body, request_config=request_config)

    triggerIncident = trigger_incident


class OpsgenieConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("opsgenie", http_client)

    def create_alert(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        message: Optional[str] = None,
        priority: str = "P2",
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        if message is not None:
            body["message"] = message
        body.setdefault("priority", priority)
        return self.invoke("createAlert", body, request_config=request_config)

    createAlert = create_alert


class SlackConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("slack", http_client)

    def send_interview_notification(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        return self.invoke("sendInterviewNotification", body, request_config=request_config)

    sendInterviewNotification = send_interview_notification

    def send_message(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        text: Optional[str] = None,
        channel: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        if text is not None:
            body["text"] = text
        if channel is not None:
            body["channel"] = channel
        return self.invoke("sendMessage", body, request_config=request_config)

    sendMessage = send_message


class TeamsConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("microsoft-teams", http_client)

    def send_message(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        title: Optional[str] = None,
        text: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        if title is not None:
            body["title"] = title
        if text is not None:
            body["text"] = text
        return self.invoke("sendMessage", body, request_config=request_config)

    sendMessage = send_message


class JiraConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("jira", http_client)

    def create_issue(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        project_key: Optional[str] = None,
        projectKey: Optional[str] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        resolved_key = projectKey or project_key or body.pop("project_key", None)
        if resolved_key is not None:
            body["projectKey"] = resolved_key
        if summary is not None:
            body["summary"] = summary
        if description is not None:
            body["description"] = description
        return self.invoke("createIssue", body, request_config=request_config)

    createIssue = create_issue


class DatadogConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("datadog", http_client)

    def send_metric(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        name: Optional[str] = None,
        value: Optional[float] = None,
        timestamp: Any = None,
        metric_type: str = "gauge",
        tags: Optional[List[str]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        if name is not None:
            body["name"] = name
        if value is not None:
            body["value"] = value
        if timestamp is not None:
            body["timestamp"] = (
                timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp
            )
        elif isinstance(body.get("timestamp"), datetime):
            body["timestamp"] = body["timestamp"].isoformat()
        body.setdefault("type", metric_type)
        if tags is not None:
            body["tags"] = tags
        return self.invoke("sendMetric", body, request_config=request_config)

    sendMetric = send_metric


class GrafanaConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("grafana", http_client)

    def create_annotation(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        text: Optional[str] = None,
        time: Optional[int] = None,
        tags: Optional[List[str]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {**(payload or {}), **kwargs}
        if text is not None:
            body["text"] = text
        if time is not None:
            body["time"] = time
        if tags is not None:
            body["tags"] = tags
        return self.invoke("createAnnotation", body, request_config=request_config)

    createAnnotation = create_annotation


class SplunkConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("splunk", http_client)

    def send_events(
        self,
        events: Union[List[Dict[str, Any]], Dict[str, Any]],
        *,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if isinstance(events, list):
            body: Dict[str, Any] = {"events": events, **kwargs}
        else:
            body = {**events, **kwargs}
        return self.invoke("sendEvents", body, request_config=request_config)

    sendEvents = send_events


class SalesforceConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("salesforce", http_client)

    def sync_contact(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body = {**(payload or {}), **kwargs}
        return self.invoke("syncContact", body, request_config=request_config)

    syncContact = sync_contact

    def upsert_record(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        object_name: Optional[str] = None,
        record: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body = {**(payload or {}), **kwargs}
        if object_name is not None:
            body["object"] = object_name
        if record is not None:
            body["record"] = record
        return self.invoke("upsertRecord", body, request_config=request_config)

    upsertRecord = upsert_record

    def read_record(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        object_name: Optional[str] = None,
        record_id: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body = {**(payload or {}), **kwargs}
        if object_name is not None:
            body["object"] = object_name
        if record_id is not None:
            body["recordId"] = record_id
        return self.invoke("readRecord", body, request_config=request_config)

    readRecord = read_record


class HubSpotConnector(BaseConnectorNamespace):
    def __init__(self, http_client: Any) -> None:
        super().__init__("hubspot", http_client)

    def read_contact(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        contact_id: Optional[str] = None,
        contactId: Optional[str] = None,
        fields: Optional[List[str]] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body = {**(payload or {}), **kwargs}
        resolved_id = contactId or contact_id or body.pop("contact_id", None)
        if resolved_id is not None:
            body["contactId"] = resolved_id
        if fields is not None:
            body["fields"] = fields
        return self.invoke("readContact", body, request_config=request_config)

    readContact = read_contact

    def upsert_contact(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        email: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body = {**(payload or {}), **kwargs}
        if email is not None:
            body["email"] = email
        return self.invoke("upsertContact", body, request_config=request_config)

    upsertContact = upsert_contact

    def sync_deal(
        self,
        payload: Optional[Dict[str, Any]] = None,
        *,
        request_config: Optional[RequestConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        body = {**(payload or {}), **kwargs}
        return self.invoke("syncDeal", body, request_config=request_config)

    syncDeal = sync_deal


def _attach_connectors(target: Any, http_client: Any) -> None:
    target.githubActions = GitHubActionsConnector(http_client)
    target.gitlabCi = GitLabCIConnector(http_client)
    target.jenkins = JenkinsConnector(http_client)
    target.circleci = CircleCIConnector(http_client)
    target.snowflake = SnowflakeConnector(http_client)
    target.bigquery = BigQueryConnector(http_client)
    target.databricks = DatabricksConnector(http_client)
    target.s3 = S3Connector(http_client)
    target.pagerduty = PagerDutyConnector(http_client)
    target.opsgenie = OpsgenieConnector(http_client)
    target.slack = SlackConnector(http_client)
    target.teams = TeamsConnector(http_client)
    target.jira = JiraConnector(http_client)
    target.datadog = DatadogConnector(http_client)
    target.grafana = GrafanaConnector(http_client)
    target.splunk = SplunkConnector(http_client)
    target.salesforce = SalesforceConnector(http_client)
    target.hubspot = HubSpotConnector(http_client)

    # Snake-case and quickstart aliases
    target.github_actions = target.githubActions
    target.github = target.githubActions
    target.gitlab_ci = target.gitlabCi
    target.gitlab = target.gitlabCi
    target.amazon_s3 = target.s3
    target.amazonS3 = target.s3
    target.microsoft_teams = target.teams
    target.microsoftTeams = target.teams


class IntegrationsService:
    """Synchronous integrations service with 16+2 connector namespaces."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client
        _attach_connectors(self, http_client)

    def get_health(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return _http_get(
            self.http_client,
            "/api/v1/integration/health",
            params=params,
            config=request_config,
        )

    def list_registry(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return _http_get(
            self.http_client,
            "/api/v1/integration/registry",
            params=params,
            config=request_config,
        )

    def register_integration(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return _http_post(
            self.http_client,
            "/api/v1/integration/registry",
            data=payload,
            config=request_config,
        )


class AsyncIntegrationsService:
    """Asynchronous integrations service."""

    def __init__(self, http_client: Any):
        self.http_client = http_client
        _attach_connectors(self, http_client)

    async def get_health(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.get(
            "/api/v1/integration/health",
            params=params,
            config=request_config,
        )

    async def list_registry(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.get(
            "/api/v1/integration/registry",
            params=params,
            config=request_config,
        )

    async def register_integration(
        self,
        payload: Dict[str, Any],
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.post(
            "/api/v1/integration/registry",
            data=payload,
            config=request_config,
        )


__all__ = [
    "SUPPORTED_CONNECTOR_NAMESPACES",
    "BaseConnectorNamespace",
    "GitHubActionsConnector",
    "GitLabCIConnector",
    "JenkinsConnector",
    "CircleCIConnector",
    "SnowflakeConnector",
    "BigQueryConnector",
    "DatabricksConnector",
    "S3Connector",
    "PagerDutyConnector",
    "OpsgenieConnector",
    "SlackConnector",
    "TeamsConnector",
    "JiraConnector",
    "DatadogConnector",
    "GrafanaConnector",
    "SplunkConnector",
    "SalesforceConnector",
    "HubSpotConnector",
    "IntegrationsService",
    "AsyncIntegrationsService",
]

"""Enterprise Intelligence services (sync and async).

Typed client for the routes under /api/v1/enterprise-intelligence. Every
method targets a route family declared in docs/api/public-api-contract.md;
the SDK route-contract check fails a release if a method targets a missing
or excluded route.

Two surfaces share one auth contract:

* Customer surface (flat methods): read workflows, runs, outputs, traces,
  deliveries and receipts; start runs (``create_run``).
* Operator families (grouped clients such as ``workflows``, ``batches``,
  ``connectors``, ``operations``): authoring, approvals, acceptance,
  connectors, SLOs and improvement. Each method's docstring names the role
  or scope it needs; the platform derives roles from the API key's creator.

Both service classes are built from the same operation classes. The async
service returns awaitables from every method, so ``await`` each call.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Union

from ...types import RequestConfig
from ...utils import HttpClientProtocol
from ._common import AsyncSender, RequestSpec, Sender, SyncSender
from ._ops_data import (
    ContextSourceOps,
    HistoricalSetOps,
    ImprovementOps,
    OperationsOps,
    RegistryOps,
    RegressionOps,
)
from ._ops_work import (
    BatchOps,
    ConnectorOps,
    DeliveryOps,
    HumanTaskOps,
    ToolBindingOps,
)
from ._ops_workflows import RunOps, WorkflowOps

JsonValue = Any


class _EnterpriseIntelligenceSurface:
    """Flat customer methods plus the grouped operator clients."""

    def __init__(self, http_client: Any, send: Sender):
        self.http_client = http_client
        self._send = send
        self.workflows = WorkflowOps(send)
        self.runs = RunOps(send)
        self.batches = BatchOps(send)
        self.deliveries = DeliveryOps(send)
        self.human_tasks = HumanTaskOps(send)
        self.connectors = ConnectorOps(send)
        self.tool_bindings = ToolBindingOps(send)
        self.context_sources = ContextSourceOps(send)
        self.historical_sets = HistoricalSetOps(send)
        self.improvement = ImprovementOps(send)
        self.regression = RegressionOps(send)
        self.operations = OperationsOps(send)
        self.registry = RegistryOps(send)

    # workflows ---------------------------------------------------------------

    def list_workflows(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self.workflows.list(params=params, request_config=request_config)

    def get_workflow(
        self, workflow_id: str, request_config: Optional[RequestConfig] = None
    ) -> Any:
        return self.workflows.get(workflow_id, request_config=request_config)

    def create_workflow(
        self,
        *,
        key: str,
        name: str,
        description: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """POST workflows (write scope; operator role). Body ``{key, name, description?}``."""
        return self.workflows.create(
            key=key,
            name=name,
            description=description,
            idempotency_key=idempotency_key,
            request_config=request_config,
        )

    # runs ----------------------------------------------------------------------

    def list_runs(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self.runs.list(params=params, request_config=request_config)

    def get_run(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self.runs.get(run_id, request_config=request_config)

    def create_run(
        self,
        *,
        workflow_version_id: str,
        input_content_id: str,
        environment_version: str,
        deadline_at: Optional[Union[str, datetime]] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """POST runs (write scope).

        Strict body ``{workflowVersionId, inputContentId, environmentVersion,
        deadlineAt?}``. ``deadline_at`` accepts an ISO string or ``datetime``.
        """
        return self.runs.create(
            workflow_version_id=workflow_version_id,
            input_content_id=input_content_id,
            environment_version=environment_version,
            deadline_at=deadline_at,
            idempotency_key=idempotency_key,
            request_config=request_config,
        )

    def get_run_output(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self.runs.get_output(run_id, request_config=request_config)

    def get_run_trace(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self.runs.get_trace(run_id, request_config=request_config)

    def get_run_delivery(
        self, run_id: str, request_config: Optional[RequestConfig] = None
    ) -> Any:
        return self.runs.get_delivery(run_id, request_config=request_config)

    def get_run_inputs(
        self, q: Optional[str] = None, request_config: Optional[RequestConfig] = None
    ) -> Any:
        return self.runs.get_inputs(q=q, request_config=request_config)

    # deliveries ---------------------------------------------------------------

    def list_deliveries(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self.deliveries.list(params=params, request_config=request_config)

    def get_delivery(
        self, delivery_id: str, request_config: Optional[RequestConfig] = None
    ) -> Any:
        return self.deliveries.get(delivery_id, request_config=request_config)

    # human review tasks --------------------------------------------------------

    def list_human_tasks(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self.human_tasks.list(params=params, request_config=request_config)

    def complete_human_task(
        self,
        task_id: str,
        *,
        action: str,
        output_content_id: str,
        evidence: JsonValue,
        expected_lock_version: int,
        correction: Optional[JsonValue] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """POST human-tasks/{task_id}/complete.

        ``action`` is one of APPROVE, REJECT, CORRECT, REQUEST_INFORMATION,
        RETRY_AUTOMATION, ESCALATE. ``evidence`` is any JSON value and is
        always sent (``None`` is sent as ``null``).
        """
        return self.human_tasks.complete(
            task_id,
            action=action,
            output_content_id=output_content_id,
            evidence=evidence,
            expected_lock_version=expected_lock_version,
            correction=correction,
            idempotency_key=idempotency_key,
            request_config=request_config,
        )

    # connectors -----------------------------------------------------------------

    def list_connectors(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self.connectors.list(params=params, request_config=request_config)

    def list_connector_receipts(
        self, connector_id: str, request_config: Optional[RequestConfig] = None
    ) -> Any:
        return self.connectors.list_receipts(connector_id, request_config=request_config)

    def get_connector_receipt(
        self,
        connector_id: str,
        receipt_id: str,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self.connectors.get_receipt(
            connector_id, receipt_id, request_config=request_config
        )

    # improvement -----------------------------------------------------------------

    def list_improvement_items(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/improvement-items",
            params=params, request_config=request_config,
        ))

    def list_evaluations(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self.improvement.list_evaluations(params=params, request_config=request_config)

    def list_regression_suites(
        self,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/regression-suites",
            params=params, request_config=request_config,
        ))

    def run_regression_suite(
        self,
        suite_id: str,
        *,
        workflow_version_id: str,
        evidence_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """POST regression-suites/{suite_id}/run. Strict body ``{workflowVersionId, evidenceId}``."""
        return self.regression.run_suite(
            suite_id,
            workflow_version_id=workflow_version_id,
            evidence_id=evidence_id,
            idempotency_key=idempotency_key,
            request_config=request_config,
        )

    # workspace -------------------------------------------------------------------

    def get_settings(self, request_config: Optional[RequestConfig] = None) -> Any:
        """Organization policy versions (read-only)."""
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/settings", request_config=request_config,
        ))

    def get_dashboard(self, request_config: Optional[RequestConfig] = None) -> Any:
        """Workspace counts: workflows, recent runs, open tasks, billing."""
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/dashboard", request_config=request_config,
        ))

    def get_health(self, request_config: Optional[RequestConfig] = None) -> Any:
        """Unauthenticated probe. A 503 raises EnterpriseIntelligenceUnavailableError
        with the health body in ``details``."""
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/health", request_config=request_config,
        ))


class EnterpriseIntelligenceService(_EnterpriseIntelligenceSurface):
    """Synchronous Enterprise Intelligence service."""

    def __init__(self, http_client: HttpClientProtocol):
        super().__init__(http_client, SyncSender(http_client))


class AsyncEnterpriseIntelligenceService(_EnterpriseIntelligenceSurface):
    """Asynchronous Enterprise Intelligence service; ``await`` every call."""

    def __init__(self, http_client: Any):
        super().__init__(http_client, AsyncSender(http_client))

"""Workflow and run operations (shared by the sync and async services)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from ...types import RequestConfig
from ._common import RequestSpec, _compact, _iso, _Ops, queue_params
from ._types import (
    AcceptanceDecision,
    ApprovalSide,
    ContentRights,
    ContextPackage,
    IncidentEvidence,
    ReplayLimits,
    WorkflowEvaluation,
    WorkflowVersionCreate,
)


class WorkflowOps(_Ops):
    """Workflow definitions, versions, approvals, activation and release gating.

    Reads need ``enterprise-intelligence.read``. Writes need
    ``enterprise-intelligence.write`` and, for most, an API key created by an
    owner, administrator or operator (operator family).
    """

    def list(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/workflows",
            params=queue_params(q, status, params), request_config=request_config,
        ))

    def get(self, workflow_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/workflows/{workflow_id}",
            {"workflow_id": workflow_id}, request_config=request_config,
        ))

    def create(
        self,
        *,
        key: str,
        name: str,
        description: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Create a workflow definition draft. Operator role. Returns 201."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/workflows",
            json=_compact({"key": key, "name": name, "description": description}),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def create_version(
        self,
        workflow_id: str,
        version: WorkflowVersionCreate,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Create an immutable version. An invalid graph answers 400
        ``WORKFLOW_GRAPH_INVALID`` with ``issues`` in the error details."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/workflows/{workflow_id}/versions",
            {"workflow_id": workflow_id}, json=dict(version),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def retire_version(
        self,
        workflow_id: str,
        version_id: str,
        *,
        expected_version: int,
        expected_definition_revision: int,
        reason: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Retire a version. ``reason`` is 8-1000 characters."""
        return self._send(RequestSpec(
            "POST",
            "/api/v1/enterprise-intelligence/workflows/{workflow_id}/versions/{version_id}/retire",
            {"workflow_id": workflow_id, "version_id": version_id},
            json={
                "expectedVersion": expected_version,
                "expectedDefinitionRevision": expected_definition_revision,
                "reason": reason,
            },
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def bind_context_package(
        self,
        workflow_id: str,
        version_id: str,
        package: ContextPackage,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Bind a context package to a version (activation requires one)."""
        return self._send(RequestSpec(
            "POST",
            "/api/v1/enterprise-intelligence/workflows/{workflow_id}/versions/{version_id}/context-package",
            {"workflow_id": workflow_id, "version_id": version_id}, json=dict(package),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def create_approval_request(
        self,
        workflow_id: str,
        *,
        version_id: str,
        evaluation_evidence_ref: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/workflows/{workflow_id}/approval-requests",
            {"workflow_id": workflow_id},
            json={"versionId": version_id, "evaluationEvidenceRef": evaluation_evidence_ref},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def get_approval_request(
        self,
        workflow_id: str,
        request_id: str,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET",
            "/api/v1/enterprise-intelligence/workflows/{workflow_id}/approval-requests/{request_id}",
            {"workflow_id": workflow_id, "request_id": request_id},
            request_config=request_config,
        ))

    @staticmethod
    def _side_path(side: ApprovalSide) -> str:
        if side == "customer":
            return "/api/v1/enterprise-intelligence/workflows/{workflow_id}/approval-requests/{request_id}/customer"
        if side == "auraone":
            return "/api/v1/enterprise-intelligence/workflows/{workflow_id}/approval-requests/{request_id}/auraone"
        raise ValueError("side must be 'customer' or 'auraone'")

    def decide_approval_request(
        self,
        workflow_id: str,
        request_id: str,
        side: ApprovalSide,
        *,
        decision: str,
        evidence: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Record one side of the dual approval (APPROVED or REJECTED)."""
        return self._send(RequestSpec(
            "POST", self._side_path(side),
            {"workflow_id": workflow_id, "request_id": request_id},
            json={"decision": decision, "evidence": evidence},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def revoke_approval_decision(
        self,
        workflow_id: str,
        request_id: str,
        side: ApprovalSide,
        *,
        evidence: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Revoke one side's decision. Sent as DELETE with ``{evidence}``."""
        return self._send(RequestSpec(
            "DELETE", self._side_path(side),
            {"workflow_id": workflow_id, "request_id": request_id},
            json={"evidence": evidence},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def activate_version(
        self,
        workflow_id: str,
        *,
        version_id: str,
        approval_request_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Activate an approved version. Answers 409
        ``ENTERPRISE_CONTEXT_PACKAGE_REQUIRED`` until a package is bound."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/workflows/{workflow_id}/activations",
            {"workflow_id": workflow_id},
            json={"versionId": version_id, "approvalRequestId": approval_request_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def record_evaluation(
        self,
        workflow_id: str,
        evaluation: WorkflowEvaluation,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/workflows/{workflow_id}/evaluations",
            {"workflow_id": workflow_id}, json=dict(evaluation),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def evaluate_release_gate(
        self,
        workflow_id: str,
        *,
        workflow_version_id: str,
        evidence_id: str,
        active_evidence_id: Optional[str] = None,
        regression_suite_id: Optional[str] = None,
        production: Optional[bool] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/workflows/{workflow_id}/release-gate",
            {"workflow_id": workflow_id},
            json=_compact({
                "workflowVersionId": workflow_version_id,
                "evidenceId": evidence_id,
                "activeEvidenceId": active_evidence_id,
                "regressionSuiteId": regression_suite_id,
                "production": production,
            }),
            idempotency_key=idempotency_key, request_config=request_config,
        ))


class RunOps(_Ops):
    """Runs: one unit of recurring work through software steps and review."""

    def list(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/runs",
            params=queue_params(q, status, params), request_config=request_config,
        ))

    def create(
        self,
        *,
        workflow_version_id: str,
        input_content_id: str,
        environment_version: str,
        deadline_at: Optional[Union[str, datetime]] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Start a run (scope: write). Returns 202; replays on a repeated key."""
        body: Dict[str, Any] = {
            "workflowVersionId": workflow_version_id,
            "inputContentId": input_content_id,
            "environmentVersion": environment_version,
        }
        if deadline_at is not None:
            body["deadlineAt"] = _iso(deadline_at)
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/runs", json=body,
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def get(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/runs/{run_id}",
            {"run_id": run_id}, request_config=request_config,
        ))

    def get_output(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/runs/{run_id}/output",
            {"run_id": run_id}, request_config=request_config,
        ))

    def get_trace(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/runs/{run_id}/trace",
            {"run_id": run_id}, request_config=request_config,
        ))

    def get_delivery(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/runs/{run_id}/delivery",
            {"run_id": run_id}, request_config=request_config,
        ))

    def get_inputs(
        self, q: Optional[str] = None, request_config: Optional[RequestConfig] = None
    ) -> Any:
        """Input content and environment versions a new run may use (write scope)."""
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/run-inputs",
            params={"q": q} if q else None, request_config=request_config,
        ))

    def get_commercial(self, run_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/runs/{run_id}/commercial",
            {"run_id": run_id}, request_config=request_config,
        ))

    def decide_acceptance(
        self,
        run_id: str,
        *,
        decision: AcceptanceDecision,
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Accept, reject or send back an outcome. Reason required unless accepted."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/runs/{run_id}/acceptance",
            {"run_id": run_id}, json=_compact({"decision": decision, "reason": reason}),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def cancel(
        self,
        run_id: str,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Cancel a run. Needs the ``enterprise-intelligence.cancel`` scope."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/runs/{run_id}/cancel",
            {"run_id": run_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def request_compensation(
        self,
        run_id: str,
        *,
        side_effect_receipt_id: str,
        reason: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/runs/{run_id}/compensations",
            {"run_id": run_id},
            json={"sideEffectReceiptId": side_effect_receipt_id, "reason": reason},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def execute_compensation(
        self,
        compensation_id: str,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/compensations/{compensation_id}/execute",
            {"compensation_id": compensation_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def report_incident(
        self,
        run_id: str,
        *,
        workflow_version_id: str,
        trigger: str,
        summary: str,
        rights: ContentRights,
        evidence: List[IncidentEvidence],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/runs/{run_id}/incidents",
            {"run_id": run_id},
            json={
                "workflowVersionId": workflow_version_id,
                "trigger": trigger,
                "summary": summary,
                "rights": rights,
                "evidence": [dict(item) for item in evidence],
            },
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def replay(
        self,
        run_id: str,
        *,
        workflow_version_id: str,
        limits: ReplayLimits,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Deterministic evaluation replay. Operator role. Returns 202."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/runs/{run_id}/replay",
            {"run_id": run_id},
            json={
                "workflowVersionId": workflow_version_id,
                "purpose": "EVALUATION",
                "limits": dict(limits),
            },
            idempotency_key=idempotency_key, request_config=request_config,
        ))

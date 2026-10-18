"""Context, historical, improvement, regression, operations and registry operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from ...types import RequestConfig
from ._common import RequestSpec, _compact, _iso, _Ops, queue_params
from ._types import (
    BaselineOutput,
    ContextSourceRegistration,
    DatasetPurpose,
    HeldOutSplit,
    HistoricalImport,
    ImprovementItem,
    Normalization,
    SloThreshold,
)


class ContextSourceOps(_Ops):
    """Customer policies, exports and files a workflow reads.

    Writes need an owner, administrator or operator. Reads and writes are
    audited.
    """

    def list(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/context-sources",
            params=queue_params(q, status, params), request_config=request_config,
        ))

    def register(
        self,
        registration: ContextSourceRegistration,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Register a stored object as an immutable source version. Returns 201."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/context-sources",
            json=dict(registration),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def get(self, source_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/context-sources/{source_id}",
            {"source_id": source_id}, request_config=request_config,
        ))

    def ingest(
        self,
        source_id: str,
        *,
        normalization: Normalization,
        source_version_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Ingest and normalize a source version (latest when not given)."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/context-sources/{source_id}/retry",
            {"source_id": source_id},
            json=_compact({
                "sourceVersionId": source_version_id,
                "normalization": dict(normalization),
            }),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def withdraw(
        self,
        source_id: str,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/context-sources/{source_id}/withdraw",
            {"source_id": source_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def apply_action(
        self,
        source_id: str,
        *,
        action: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """PATCH ``{"action": "withdraw" | "delete"}``."""
        return self._send(RequestSpec(
            "PATCH", "/api/v1/enterprise-intelligence/context-sources/{source_id}",
            {"source_id": source_id}, json={"action": action},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def delete(
        self,
        source_id: str,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "DELETE", "/api/v1/enterprise-intelligence/context-sources/{source_id}",
            {"source_id": source_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))


class HistoricalSetOps(_Ops):
    """Past cases with accepted outcomes, used for datasets and baselines."""

    def list(self, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/historical-sets",
            request_config=request_config,
        ))

    def import_set(
        self,
        set_import: HistoricalImport,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Import ``records`` or ``sourceText`` + ``format``. Returns 201."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/historical-sets",
            json=dict(set_import),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def get(self, set_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/historical-sets/{set_id}",
            {"set_id": set_id}, request_config=request_config,
        ))

    def list_examples(self, set_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/historical-sets/{set_id}/examples",
            {"set_id": set_id}, request_config=request_config,
        ))

    def validate(
        self,
        set_id: str,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/historical-sets/{set_id}/validate",
            {"set_id": set_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def accept(
        self,
        set_id: str,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/historical-sets/{set_id}/accept",
            {"set_id": set_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def create_dataset(
        self,
        set_id: str,
        *,
        purpose: DatasetPurpose,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/historical-sets/{set_id}/dataset",
            {"set_id": set_id}, json={"purpose": purpose},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def list_baselines(self, set_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/historical-sets/{set_id}/baseline",
            {"set_id": set_id}, request_config=request_config,
        ))

    def prepare_baseline(
        self,
        set_id: str,
        *,
        split: HeldOutSplit,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Fetch the held-out examples a baseline must answer."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/historical-sets/{set_id}/baseline",
            {"set_id": set_id}, json={"split": split},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def evaluate_baseline(
        self,
        set_id: str,
        *,
        model_ref: str,
        split: HeldOutSplit,
        outputs: List[BaselineOutput],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Score outputs against accepted outcomes; must cover the split once."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/historical-sets/{set_id}/baseline",
            {"set_id": set_id},
            json={
                "modelRef": model_ref,
                "split": split,
                "outputs": [dict(output) for output in outputs],
            },
            idempotency_key=idempotency_key, request_config=request_config,
        ))


class ImprovementOps(_Ops):
    """Improvement backlog and activation evaluations."""

    def list_items(self, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/improvement-items",
            request_config=request_config,
        ))

    def create_item(
        self,
        item: ImprovementItem,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/improvement-items", json=dict(item),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def list_evaluations(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/evaluations",
            params=queue_params(q, status, params), request_config=request_config,
        ))


class RegressionOps(_Ops):
    """Accepted outcomes and corrections kept as tests for later versions."""

    def list_candidates(self, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/regression-candidates",
            request_config=request_config,
        ))

    def create_candidate(
        self,
        *,
        incident_id: str,
        evaluation_suite_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/regression-candidates",
            json={"incidentId": incident_id, "evaluationSuiteId": evaluation_suite_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def review_candidate(
        self,
        candidate_id: str,
        *,
        decision: str,
        purpose: DatasetPurpose,
        reason: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Approve or deny. Owner, administrator or reviewer role."""
        return self._send(RequestSpec(
            "POST",
            "/api/v1/enterprise-intelligence/regression-candidates/{candidate_id}/review",
            {"candidate_id": candidate_id},
            json={"decision": decision, "purpose": purpose, "reason": reason},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def list_suites(self, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/regression-suites",
            request_config=request_config,
        ))

    def run_suite(
        self,
        suite_id: str,
        *,
        workflow_version_id: str,
        evidence_id: str,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/regression-suites/{suite_id}/run",
            {"suite_id": suite_id},
            json={"workflowVersionId": workflow_version_id, "evidenceId": evidence_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def export_suite(self, suite_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/regression-suites/{suite_id}/export",
            {"suite_id": suite_id}, request_config=request_config,
        ))


class OperationsOps(_Ops):
    """Service-level metrics and agreed service levels (SLOs)."""

    def get_metrics(
        self,
        *,
        program_id: str,
        workflow_id: str,
        workflow_version_id: str,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/operations/metrics",
            params={
                "programId": program_id,
                "workflowId": workflow_id,
                "workflowVersionId": workflow_version_id,
            },
            request_config=request_config,
        ))

    def list_slos(
        self,
        *,
        program_id: str,
        workflow_id: str,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/operations/slos",
            params={"programId": program_id, "workflowId": workflow_id},
            request_config=request_config,
        ))

    def create_slo(
        self,
        *,
        program_id: str,
        workflow_id: str,
        thresholds: Dict[str, List[SloThreshold]],
        service_credit_policy: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Draft an SLO. ``thresholds`` needs every area in ``SLO_AREAS``."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/operations/slos",
            json=_compact({
                "programId": program_id,
                "workflowId": workflow_id,
                "thresholds": {area: [dict(t) for t in rows] for area, rows in thresholds.items()},
                "serviceCreditPolicy": service_credit_policy,
            }),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def approve_slo(
        self,
        slo_id: str,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Approve a draft SLO. Customer owner role."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/operations/slos/{slo_id}/approve",
            {"slo_id": slo_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def activate_slo(
        self,
        slo_id: str,
        *,
        effective_from: Union[str, datetime],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Activate an approved SLO. Owner or administrator."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/operations/slos/{slo_id}/activate",
            {"slo_id": slo_id}, json={"effectiveFrom": _iso(effective_from)},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def get_slo_release_gate(
        self,
        *,
        program_id: str,
        workflow_id: str,
        at: Optional[Union[str, datetime]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/operations/slos/release-gate",
            params=_compact({
                "programId": program_id,
                "workflowId": workflow_id,
                "at": _iso(at) if at is not None else None,
            }),
            request_config=request_config,
        ))


class RegistryOps(_Ops):
    """Governed models, policies, prompts and tools.

    Each write is one ``action`` of a discriminated union, sent as given.
    """

    def get_node_options(self, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/registry/node-options",
            request_config=request_config,
        ))

    def models(
        self,
        request: Dict[str, Any],
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """``action``: create, create-version or release."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/registry/models", json=dict(request),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def policies(
        self,
        request: Dict[str, Any],
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """``action``: create-version or approve."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/registry/policies", json=dict(request),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def prompts(
        self,
        request: Dict[str, Any],
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """``action``: create, create-version or approve."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/registry/prompts", json=dict(request),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def tools(
        self,
        request: Dict[str, Any],
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """``action``: create, create-version or approve."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/registry/tools", json=dict(request),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

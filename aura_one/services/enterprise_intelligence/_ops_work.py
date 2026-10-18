"""Batch, delivery, human task, connector and tool binding operations."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ...types import RequestConfig
from ._common import RequestSpec, _compact, _Ops, queue_params
from ._types import (
    BatchAcceptanceSelection,
    BatchItem,
    IngestionContract,
    IngestionSource,
    ToolBinding,
)


def build_ingest_parts(
    workflow_version_id: str,
    contract: IngestionContract,
    sources: Sequence[IngestionSource],
) -> Tuple[Dict[str, str], List[Tuple[str, Tuple[str, bytes, str]]]]:
    """Multipart form fields and files for batch ingestion, in source order."""
    if not sources:
        raise ValueError("ingest requires at least one source")
    form = {
        "workflowVersionId": workflow_version_id,
        "contract": json.dumps(contract),
        "sources": json.dumps(
            [
                {
                    "sourceId": source["sourceId"],
                    "fileName": source["fileName"],
                    "mediaType": source["mediaType"],
                }
                for source in sources
            ]
        ),
    }
    files: List[Tuple[str, Tuple[str, bytes, str]]] = []
    for source in sources:
        content = source["content"]
        data = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        files.append(("file", (source["fileName"], data, source["mediaType"])))
    return form, files


class BatchOps(_Ops):
    """Batches: a queue of work units submitted together, one run per item."""

    def list(self, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/batches", request_config=request_config,
        ))

    def submit(
        self,
        *,
        workflow_version_id: str,
        input_contract: Any,
        items: List[BatchItem],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Submit 1-10,000 items. Returns 202."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/batches",
            json={
                "workflowVersionId": workflow_version_id,
                "inputContract": input_contract,
                "items": [dict(item) for item in items],
            },
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def ingest(
        self,
        *,
        workflow_version_id: str,
        contract: IngestionContract,
        sources: Sequence[IngestionSource],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Upload source files as one batch (multipart/form-data). Returns 202."""
        form, files = build_ingest_parts(workflow_version_id, contract, sources)
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/batches/ingest",
            form=form, files=files,
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def get(self, batch_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/batches/{batch_id}",
            {"batch_id": batch_id}, request_config=request_config,
        ))

    def list_items(self, batch_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/batches/{batch_id}/items",
            {"batch_id": batch_id}, request_config=request_config,
        ))

    def retry(
        self,
        batch_id: str,
        *,
        item_ids: Optional[List[str]] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Retry items; omit ``item_ids`` to let the server select them."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/batches/{batch_id}/retry",
            {"batch_id": batch_id},
            json={"itemIds": item_ids} if item_ids else None,
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def cancel(
        self,
        batch_id: str,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Cancel open runs. Needs the cancel scope or an operator role."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/batches/{batch_id}/cancel",
            {"batch_id": batch_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def decide_acceptance(
        self,
        batch_id: str,
        *,
        selections: List[BatchAcceptanceSelection],
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Accept, reject or send back items, each against a delivery version."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/batches/{batch_id}/acceptance",
            {"batch_id": batch_id},
            json={"selections": [dict(selection) for selection in selections]},
            idempotency_key=idempotency_key, request_config=request_config,
        ))


class DeliveryOps(_Ops):
    """Deliveries: the accepted output in the agreed format."""

    def list(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/deliveries",
            params=queue_params(q, status, params), request_config=request_config,
        ))

    def get(self, delivery_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/deliveries/{delivery_id}",
            {"delivery_id": delivery_id}, request_config=request_config,
        ))

    def dispose(
        self,
        delivery_id: str,
        *,
        action: str,
        note: Optional[str] = None,
        taxonomy_version: Optional[str] = None,
        reason_code: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Dispose of a Program delivery (accept, reject, rework). Operator role.

        Deliveries that belong to a run answer 409: use
        ``runs.decide_acceptance`` for those.
        """
        return self._send(RequestSpec(
            "PATCH", "/api/v1/enterprise-intelligence/deliveries/{delivery_id}",
            {"delivery_id": delivery_id},
            json=_compact({
                "action": action,
                "note": note,
                "taxonomyVersion": taxonomy_version,
                "reasonCode": reason_code,
            }),
            idempotency_key=idempotency_key, request_config=request_config,
        ))


class HumanTaskOps(_Ops):
    """Human tasks: exceptions and reviews that qualified people resolve."""

    def list(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/human-tasks",
            params=queue_params(q, status, params), request_config=request_config,
        ))

    def get(self, task_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/human-tasks/{task_id}",
            {"task_id": task_id}, request_config=request_config,
        ))

    def complete(
        self,
        task_id: str,
        *,
        action: str,
        output_content_id: str,
        evidence: Any,
        expected_lock_version: int,
        correction: Optional[Any] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Resolve a task. ``evidence`` is always sent (``None`` as ``null``)."""
        body: Dict[str, Any] = {
            "action": action,
            "outputContentId": output_content_id,
            "evidence": evidence,
            "expectedLockVersion": expected_lock_version,
        }
        if correction is not None:
            body["correction"] = correction
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/human-tasks/{task_id}/complete",
            {"task_id": task_id}, json=body,
            idempotency_key=idempotency_key, request_config=request_config,
        ))


class ConnectorOps(_Ops):
    """Connectors to customer systems and receipts of every call made.

    Create, authorize and revoke need an owner or administrator; the sandbox
    test also accepts operators.
    """

    def list(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/connectors",
            params=queue_params(q, status, params), request_config=request_config,
        ))

    def create(
        self,
        *,
        name: str,
        provider: str,
        secret_reference_id: str,
        environment: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/connectors",
            json=_compact({
                "name": name,
                "provider": provider,
                "environment": environment,
                "secretReferenceId": secret_reference_id,
            }),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def get(self, connector_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/connectors/{connector_id}",
            {"connector_id": connector_id}, request_config=request_config,
        ))

    def apply_action(
        self,
        connector_id: str,
        *,
        action: str = "revoke",
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """PATCH ``{"action": "revoke"}`` (same effect as :meth:`revoke`)."""
        return self._send(RequestSpec(
            "PATCH", "/api/v1/enterprise-intelligence/connectors/{connector_id}",
            {"connector_id": connector_id}, json={"action": action},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def authorize(
        self,
        connector_id: str,
        step: Dict[str, Any],
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """OAuth step: ``{"action": "START" | "CALLBACK" | "REVOKE", ...}``."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/connectors/{connector_id}/authorize",
            {"connector_id": connector_id}, json=dict(step),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def test(
        self,
        connector_id: str,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        """Sandbox probe. A failed probe answers 424 with the result."""
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/connectors/{connector_id}/test",
            {"connector_id": connector_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def revoke(
        self,
        connector_id: str,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/connectors/{connector_id}/revoke",
            {"connector_id": connector_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def list_receipts(
        self,
        connector_id: str,
        *,
        workflow_id: Optional[str] = None,
        run_id: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/connectors/{connector_id}/receipts",
            {"connector_id": connector_id},
            params=_compact({"workflowId": workflow_id, "runId": run_id}) or None,
            request_config=request_config,
        ))

    def get_receipt(
        self,
        connector_id: str,
        receipt_id: str,
        *,
        workflow_id: Optional[str] = None,
        run_id: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET",
            "/api/v1/enterprise-intelligence/connectors/{connector_id}/receipts/{receipt_id}",
            {"connector_id": connector_id, "receipt_id": receipt_id},
            params=_compact({"workflowId": workflow_id, "runId": run_id}) or None,
            request_config=request_config,
        ))


class ToolBindingOps(_Ops):
    """Tool bindings: which connector tool a workflow version may call."""

    def list(
        self,
        q: Optional[str] = None,
        status: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/tool-bindings",
            params=queue_params(q, status, params), request_config=request_config,
        ))

    def create(
        self,
        binding: ToolBinding,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "POST", "/api/v1/enterprise-intelligence/tool-bindings", json=dict(binding),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def get(self, binding_id: str, request_config: Optional[RequestConfig] = None) -> Any:
        return self._send(RequestSpec(
            "GET", "/api/v1/enterprise-intelligence/tool-bindings/{binding_id}",
            {"binding_id": binding_id}, request_config=request_config,
        ))

    def update(
        self,
        binding_id: str,
        changes: ToolBinding,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "PATCH", "/api/v1/enterprise-intelligence/tool-bindings/{binding_id}",
            {"binding_id": binding_id}, json=dict(changes),
            idempotency_key=idempotency_key, request_config=request_config,
        ))

    def disable(
        self,
        binding_id: str,
        *,
        idempotency_key: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Any:
        return self._send(RequestSpec(
            "DELETE", "/api/v1/enterprise-intelligence/tool-bindings/{binding_id}",
            {"binding_id": binding_id},
            idempotency_key=idempotency_key, request_config=request_config,
        ))

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum
import time
import uuid
import os
import secrets
import httpx
from httpx import HTTPError, TimeoutException


class EvaluationStatus(Enum):
	QUEUED = "queued"
	RUNNING = "running"
	COMPLETED = "completed"
	FAILED = "failed"


@dataclass
class EvaluationResult:
	id: str
	status: EvaluationStatus
	score: Optional[float] = None
	metrics: Optional[Dict[str, float]] = None
	artifacts_url: Optional[str] = None


@dataclass
class Template:
	id: str
	name: str
	version: str
	domain: Optional[str] = None


class AuraClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.auraone.ai",
        org_id: Optional[str] = None,
        timeout: float = 10.0,
        retry_attempts: int = 3,
        backoff_ms: int = 300,
    ):
        """
        Python SDK client for AuraOne.

        Args:
            api_key: API key or bearer JWT. If None, 'test' is used for local.
            base_url: Base API URL (no trailing slash required).
            org_id: Organization/tenant identifier; defaults to 'public'.
            timeout: Per-request timeout in seconds.
            retry_attempts: How many times to retry transient failures (>=500 or timeouts).
            backoff_ms: Base backoff in milliseconds; grows linearly by attempt.
        """
        # Public attributes
        self.api_key = api_key or "test"
        self.base_url = base_url.rstrip("/")
        self.org_id = org_id or "public"
        # Back-compat private aliases expected by tests/tooling
        self._api_key = self.api_key
        self._base_url = self.base_url
        self._org_id = self.org_id
        self._client = httpx.Client(timeout=timeout)
        self._retry_attempts = max(1, retry_attempts)
        self._backoff_ms = max(0, backoff_ms)

    def _headers(self) -> Dict[str, str]:
        h = {"X-Org-Id": self.org_id}
        h["Authorization"] = f"Bearer {self.api_key}"
        if self._otel_enabled():
            h["traceparent"] = self._traceparent()
        return h

    def _otel_enabled(self) -> bool:
        if os.environ.get("OTEL_DISABLED") == "true":
            return False
        if os.environ.get("OTEL_ENABLED") == "true":
            return True
        return (os.environ.get("NODE_ENV") or "development") == "production"

    def _traceparent(self) -> str:
        trace_id = uuid.uuid4().hex
        span_id = secrets.token_hex(8)
        return f"00-{trace_id}-{span_id}-01"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        idempotency: bool = False,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        hdrs = {**self._headers(), **(headers or {})}
        if idempotency:
            hdrs.setdefault("X-Idempotency-Key", str(uuid.uuid4()))

        last_exc: Optional[Exception] = None
        for attempt in range(1, self._retry_attempts + 1):
            try:
                # Some tests inject a lightweight client without a generic 'request' method.
                # Support both httpx.Client.request and simple .get/.post mocks.
                if hasattr(self._client, "request"):
                    resp = self._client.request(method, url, json=json, params=params, headers=hdrs)
                else:
                    call = getattr(self._client, method.lower())
                    resp = call(url, json=json, params=params, headers=hdrs)
                # Retry on 5xx when available on the response object
                status_code = getattr(resp, "status_code", None)
                if isinstance(status_code, int) and 500 <= status_code < 600:
                    raise HTTPError(f"Server error {status_code}")
                return resp
            except (TimeoutException, HTTPError) as exc:
                last_exc = exc
                if attempt >= self._retry_attempts:
                    raise
                # Linear backoff (simple, deterministic)
                time.sleep((self._backoff_ms * attempt) / 1000.0)
        # Should not reach here
        raise last_exc or RuntimeError("request failed without exception")

    def evaluate(
        self,
        template_id: str,
        agent_bundle_url: str,
        reward_spec_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        wait: bool = True,
        timeout: int = 300,
    ) -> EvaluationResult:
        payload: Dict[str, Any] = {
            "template_id": template_id,
            "agent_bundle_url": agent_bundle_url,
        }
        if reward_spec_id:
            payload["reward_spec_id"] = reward_spec_id
        if config:
            payload["config"] = config
        r = self._request("POST", "/v1/evaluations", json=payload, headers={}, idempotency=True)
        r.raise_for_status()
        data = r.json()
        status = data.get("status") or data.get("state") or "queued"
        result = EvaluationResult(id=data["id"], status=EvaluationStatus(status))
        if not wait:
            return result
        # Poll
        end = time.time() + timeout
        while time.time() < end:
            res = self.get_status(result.id)
            if res.status in (EvaluationStatus.COMPLETED, EvaluationStatus.FAILED):
                return res
            time.sleep(0.5)
        return self.get_status(result.id)

    def evaluate_robust(
        self,
        template_id: str,
        agent_bundle_url: str,
        *,
        reward_spec_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        backoff_ms: int = 500,
        wait: bool = False,
    ) -> EvaluationResult:
        """Create an evaluation with client-side retry/backoff (POST only).

        This mirrors TS SDK's robust create helper, and always uses idempotency keys.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                return self.evaluate(
                    template_id=template_id,
                    agent_bundle_url=agent_bundle_url,
                    reward_spec_id=reward_spec_id,
                    config=config,
                    wait=wait,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt >= max_retries:
                    raise
                time.sleep((backoff_ms * attempt) / 1000.0)
        # Should not reach here
        if last_exc:
            raise last_exc
        raise RuntimeError("evaluate_robust failed without exception")

    def get_status(self, evaluation_id: str) -> EvaluationResult:
        r = self._request("GET", f"/v1/evaluations/{evaluation_id}")
        r.raise_for_status()
        data = r.json()
        status = EvaluationStatus((data.get("status") or data.get("state") or "queued"))
        return EvaluationResult(
            id=data["id"],
            status=status,
            score=data.get("score"),
            metrics=data.get("metrics"),
            artifacts_url=data.get("artifacts_url"),
        )

    def cancel(self, evaluation_id: str) -> EvaluationResult:
        r = self._request("POST", f"/v1/evaluations/{evaluation_id}:cancel")
        r.raise_for_status()
        raw = r.json()
        # Some APIs return the updated resource; otherwise fetch
        if isinstance(raw, dict) and raw.get("id"):
            s = raw.get("status") or raw.get("state") or "cancelled"
            return EvaluationResult(
                id=raw["id"],
                status=EvaluationStatus(s),
                score=raw.get("score"),
                metrics=raw.get("metrics"),
                artifacts_url=raw.get("artifacts_url"),
            )
        return self.get_status(evaluation_id)

    def list_templates(self, domain: Optional[str] = None, page: int = 1, per_page: int = 20) -> List[Template]:
        params: Dict[str, Any] = {"page": page, "per_page": per_page}
        if domain:
            params["domain"] = domain
        r = self._request("GET", "/v1/templates", params=params)
        r.raise_for_status()
        payload = r.json()
        data = payload if isinstance(payload, list) else payload.get("templates") or payload.get("data") or []
        items: List[Template] = []
        for t in data:
            items.append(Template(id=t.get("id"), name=t["name"], version=t.get("version") or "1.0.0", domain=t.get("domain")))
        return items

    def get_template(self, template_id: str) -> Template:
        r = self._request("GET", f"/v1/templates/{template_id}")
        r.raise_for_status()
        raw = r.json()
        t = raw.get("template") if isinstance(raw, dict) and raw.get("template") else raw
        return Template(id=t.get("id"), name=t["name"], version=t.get("version") or "1.0.0", domain=t.get("domain"))

    def get_quotas(self) -> Dict[str, Any]:
        r = self._request("GET", "/v1/quotas")
        r.raise_for_status()
        return r.json()

    def get_attestation(self, evaluation_id: str) -> Dict[str, Any]:
        r = self._request("GET", f"/v1/attestations/{evaluation_id}")
        r.raise_for_status()
        return r.json()

    # ---- Advanced endpoints: analytics, algorithms, benchmarks, safety, admin ----

    def get_evaluation_analytics(self, timeframe: str = "24h") -> Dict[str, Any]:
        r = self._request("GET", "/v1/analytics/evaluation-metrics", params={"timeframe": timeframe})
        r.raise_for_status()
        return r.json()

    def get_template_analytics(self, template_id: str, time_range: str = "30d") -> Dict[str, Any]:
        r = self._request("GET", f"/v1/templates/{template_id}/analytics", params={"timeRange": time_range})
        r.raise_for_status()
        return r.json()

    def get_org_templates_analytics(self, org_id: Optional[str] = None, time_range: str = "30d") -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/v1/organizations/{oid}/templates/analytics", params={"timeRange": time_range})
        r.raise_for_status()
        return r.json()

    def get_algorithm_metrics(self, org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/v1/organizations/{oid}/algorithms/metrics")
        r.raise_for_status()
        return r.json()

    def compare_algorithms(self, algorithm_ids: List[str], metrics: Optional[List[str]] = None) -> Dict[str, Any]:
        payload = {"algorithm_ids": algorithm_ids, "metrics": metrics or ["accuracy", "precision", "recall", "f1Score"]}
        r = self._request("POST", "/v1/algorithms/compare", json=payload)
        r.raise_for_status()
        return r.json()

    def get_competitive_benchmarks(self) -> Dict[str, Any]:
        r = self._request("GET", "/v1/competitive/benchmarks")
        r.raise_for_status()
        return r.json()

    def get_safety_metrics(self, org_id: Optional[str] = None, time_range: str = "30d") -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/v1/organizations/{oid}/safety/metrics", params={"timeRange": time_range})
        r.raise_for_status()
        return r.json()

    def get_safety_incidents(self, org_id: Optional[str] = None, status: str = "open") -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/v1/organizations/{oid}/safety/incidents", params={"status": status})
        r.raise_for_status()
        return r.json()

    def get_compliance_reports(self, org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/v1/organizations/{oid}/safety/compliance")
        r.raise_for_status()
        return r.json()

    def get_organization_metrics(self, org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/v1/admin/organizations/{oid}/metrics")
        r.raise_for_status()
        return r.json()

    def get_system_health(self) -> Dict[str, Any]:
        r = self._request("GET", "/v1/admin/system/health")
        r.raise_for_status()
        return r.json()

    # ---- Federation endpoints ----

    def get_federation_nodes(self, org_id: Optional[str] = None) -> Dict[str, Any]:
        """Get federation nodes for an organization."""
        oid = org_id or self.org_id
        r = self._request("GET", f"/v1/organizations/{oid}/federation/nodes")
        r.raise_for_status()
        return r.json()

    def get_federation_rounds(self, org_id: Optional[str] = None, limit: int = 10, status: Optional[str] = None) -> Dict[str, Any]:
        """Get federation rounds for an organization."""
        oid = org_id or self.org_id
        params = {"limit": limit}
        if status:
            params["status"] = status
        r = self._request("GET", f"/v1/organizations/{oid}/federation/rounds", params=params)
        r.raise_for_status()
        return r.json()

    def get_federation_metrics(self, org_id: Optional[str] = None, timeframe: str = "30d") -> Dict[str, Any]:
        """Get federation metrics for an organization."""
        oid = org_id or self.org_id
        r = self._request("GET", f"/v1/organizations/{oid}/federation/metrics", params={"timeframe": timeframe})
        r.raise_for_status()
        return r.json()

    # ---- Chemistry & 3D Visualization ----

    def parse_molecular_file(self, file_path: str, format_type: Optional[str] = None, enable_caching: bool = True) -> Dict[str, Any]:
        """Parse molecular file and extract chemical structure data."""
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {}
            if format_type:
                data['format_type'] = format_type
            if enable_caching:
                data['enable_caching'] = 'true'
            
            r = self._request("POST", "/v1/chemistry/parse-molecular-file-optimized", files=files, data=data)
            r.raise_for_status()
            return r.json()

    def get_chemistry_performance_status(self) -> Dict[str, Any]:
        """Get chemistry service performance status."""
        r = self._request("GET", "/v1/chemistry/performance-status")
        r.raise_for_status()
        return r.json()

    # ---- RFT Automation (Reward Function Tooling) ----

    def generate_rft_environment(self, evaluation_id: str, configuration: Dict[str, Any]) -> Dict[str, Any]:
        """Generate RFT environment scaffold for an evaluation."""
        payload = {
            "evaluation_id": evaluation_id,
            "configuration": configuration
        }
        r = self._request("POST", "/v1/rft/generate-environment", json=payload)
        r.raise_for_status()
        return r.json()

    def build_reward_function(self, strategy: str, metrics: List[str], configuration: Dict[str, Any]) -> Dict[str, Any]:
        """Build reward function configuration."""
        payload = {
            "strategy": strategy,
            "metrics": metrics,
            "configuration": configuration
        }
        r = self._request("POST", "/v1/rft/build-reward", json=payload)
        r.raise_for_status()
        return r.json()

    # ---- Rewards & Compilation ----

    def compile_reward(self, yaml_spec: str) -> Dict[str, Any]:
        """Compile and validate reward function YAML specification."""
        payload = {"yaml_spec": yaml_spec}
        r = self._request("POST", "/v1/rewards/compile", json=payload)
        r.raise_for_status()
        return r.json()

    def list_reward_specs(self) -> Dict[str, Any]:
        """List available reward specifications."""
        r = self._request("GET", "/v1/rewards")
        r.raise_for_status()
        return r.json()

    # ---- Advanced Analytics ----

    def get_template_usage_metrics(self, template_id: str) -> Dict[str, Any]:
        """Get detailed usage metrics for a template."""
        r = self._request("GET", f"/v1/templates/{template_id}/usage-metrics")
        r.raise_for_status()
        return r.json()

    # ---- Batch Operations ----

    def create_multiple_evaluations(self, evaluation_requests: List[Dict[str, Any]]) -> List[EvaluationResult]:
        """Create multiple evaluations in batch."""
        results = []
        for req in evaluation_requests:
            try:
                result = self.evaluate(
                    template_id=req["template_id"],
                    agent_bundle_url=req["agent_bundle_url"],
                    reward_spec_id=req.get("reward_spec_id"),
                    config=req.get("config", {})
                )
                results.append(result)
            except Exception as e:
                # Continue with other evaluations even if one fails
                print(f"Failed to create evaluation: {e}")
                results.append(EvaluationResult(
                    id=f"failed-{len(results)}",
                    status=EvaluationStatus.FAILED,
                    score=None,
                    metrics=None
                ))
        return results

    def wait_for_multiple_completions(self, evaluation_ids: List[str], timeout_seconds: int = 300) -> List[EvaluationResult]:
        """Wait for multiple evaluations to complete."""
        results = []
        for eval_id in evaluation_ids:
            try:
                result = self.wait_for_completion(eval_id, timeout_seconds)
                results.append(result)
            except Exception as e:
                print(f"Failed to wait for evaluation {eval_id}: {e}")
                results.append(EvaluationResult(
                    id=eval_id,
                    status=EvaluationStatus.FAILED,
                    score=None,
                    metrics=None
                ))
        return results

    # ---- Context Managers ----

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources."""
        if hasattr(self, '_client'):
            self._client.close()

    # ---- Utility helpers ----

    def wait_for_completion(self, evaluation_id: str, timeout_seconds: int = 300, poll_interval: float = 1.0) -> EvaluationResult:
        """Poll evaluation status until terminal state or timeout.

        Terminal states: COMPLETED, FAILED, CANCELLED (if exposed by API).
        """
        end = time.time() + timeout_seconds
        while time.time() < end:
            res = self.get_status(evaluation_id)
            if res.status in (
                EvaluationStatus.COMPLETED,
                EvaluationStatus.FAILED,
            ):
                return res
            # Some APIs may return cancelled
            try:
                if res.status.name == "CANCELLED":  # type: ignore[attr-defined]
                    return res
            except Exception:
                pass
            time.sleep(max(0.1, poll_interval))
        return self.get_status(evaluation_id)

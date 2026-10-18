from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum
import time
import uuid
import os
import secrets
import base64
import warnings
import httpx
from httpx import HTTPError, TimeoutException


class EvaluationStatus(Enum):
	QUEUED = "queued"
	PENDING = "pending"
	RUNNING = "running"
	COMPLETED = "completed"
	FAILED = "failed"
	CANCELLED = "cancelled"
	UNKNOWN = "unknown"

	@classmethod
	def _missing_(cls, value):
		# Unknown platform statuses map to UNKNOWN instead of raising (F13).
		return cls.UNKNOWN


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


def _metrics_to_dict(metrics):
    """Platform returns metrics as [{name, value, timestamp}]; expose a dict."""
    if isinstance(metrics, list):
        out = {}
        for item in metrics:
            if isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("value"), (int, float)):
                out[item["name"]] = item["value"]
        return out or None
    return metrics


class AuraClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        org_id: Optional[str] = None,
        timeout: float = 10.0,
        retry_attempts: int = 3,
        backoff_ms: int = 300,
    ):
        """
        Python SDK client for AuraOne.

        Args:
            api_key: API key or bearer JWT. Resolved from this argument, then
                the AURAONE_API_KEY environment variable, then AURA_API_KEY
                (deprecated; emits a DeprecationWarning). Required — a client
                with no credential raises ValueError.
            base_url: Base API URL (no trailing slash required). Resolved from
                this argument, then AURAONE_BASE_URL, then https://api.auraone.ai.
            org_id: Organization/tenant assertion, checked server-side against
                the API key's organization (never defaulted to 'public').
                Resolved from this argument, then AURAONE_ORG_ID.
            timeout: Per-request timeout in seconds.
            retry_attempts: How many times to retry transient failures (>=500 or timeouts).
            backoff_ms: Base backoff in milliseconds; grows linearly by attempt.

        Raises:
            ValueError: when no credential is found in the argument or the
                environment.
        """
        # Public attributes. No unsafe defaults: a credential is required for
        # authenticated calls; org is an optional assertion checked against
        # the API key's organization server-side (never "public").
        self.api_key = self._resolve_api_key(api_key)
        resolved_base_url = (
            base_url
            or os.environ.get("AURAONE_BASE_URL")
            or os.environ.get("AURA_BASE_URL")
            or "https://api.auraone.ai"
        )
        self.base_url = resolved_base_url.rstrip("/")
        self.org_id = (
            org_id
            if org_id is not None
            else (os.environ.get("AURAONE_ORG_ID") or os.environ.get("AURA_ORG_ID"))
        )
        # Back-compat private aliases expected by tests/tooling
        self._api_key = self.api_key
        self._base_url = self.base_url
        self._org_id = self.org_id
        self._client = httpx.Client(timeout=timeout)
        self._retry_attempts = max(1, retry_attempts)
        self._backoff_ms = max(0, backoff_ms)
        self._enterprise_intelligence = None
        self._graphql = None
        self._integrations = None

    @staticmethod
    def _resolve_api_key(api_key: Optional[str]) -> str:
        """Resolve the credential: argument, then AURAONE_API_KEY, then the
        deprecated AURA_API_KEY fallback (which warns)."""
        if api_key:
            return api_key
        env_key = os.environ.get("AURAONE_API_KEY")
        if env_key:
            return env_key
        legacy_key = os.environ.get("AURA_API_KEY")
        if legacy_key:
            warnings.warn(
                "AURA_API_KEY is deprecated; set AURAONE_API_KEY instead",
                DeprecationWarning,
                stacklevel=3,
            )
            return legacy_key
        raise ValueError(
            "AuraClient requires an API key: pass api_key or set AURAONE_API_KEY"
        )

    @property
    def enterprise_intelligence(self):
        """Enterprise Intelligence service (lazy; see aura.enterprise_intelligence)."""
        if self._enterprise_intelligence is None:
            from .enterprise_intelligence import EnterpriseIntelligenceService

            self._enterprise_intelligence = EnterpriseIntelligenceService(self)
        return self._enterprise_intelligence

    @property
    def graphql(self):
        """GraphQL service targeting /api/graphql."""
        if self._graphql is None:
            from .services.graphql import GraphQLService

            self._graphql = GraphQLService(self)
        return self._graphql

    @property
    def integrations(self):
        """Integrations service with 16+2 connector namespaces."""
        if self._integrations is None:
            from .services.integrations import IntegrationsService

            self._integrations = IntegrationsService(self)
        return self._integrations

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {}
        # ak_ keys authenticate via X-API-Key (cookieless; CSRF-exempt).
        # Other tokens are treated as JWTs and sent as Bearer.
        if self.api_key:
            if self.api_key.startswith("ak_"):
                h["X-API-Key"] = self.api_key
            else:
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
        if self.org_id:
            params = {**(params or {}), "orgId": self.org_id}
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
        r = self._request("POST", "/api/v1/evaluations", json=payload, headers={}, idempotency=True)
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
        r = self._request("GET", f"/api/v1/evaluations/{evaluation_id}")
        r.raise_for_status()
        data = r.json()
        status = EvaluationStatus((data.get("status") or data.get("state") or "queued"))
        return EvaluationResult(
            id=data["id"],
            status=status,
            score=data.get("score"),
            metrics=_metrics_to_dict(data.get("metrics")),
            artifacts_url=data.get("artifacts_url"),
        )

    def cancel(self, evaluation_id: str) -> EvaluationResult:
        r = self._request("POST", f"/api/v1/evaluations/{evaluation_id}/cancel")
        r.raise_for_status()
        raw = r.json()
        # Some APIs return the updated resource; otherwise fetch
        if isinstance(raw, dict) and (raw.get("id") or raw.get("evaluation_id")):
            s = raw.get("status") or raw.get("state") or "cancelled"
            return EvaluationResult(
                id=raw.get("id") or raw["evaluation_id"],
                status=EvaluationStatus(s),
                score=raw.get("score"),
                metrics=_metrics_to_dict(raw.get("metrics")),
                artifacts_url=raw.get("artifacts_url"),
            )
        return self.get_status(evaluation_id)

    def list_templates(self, domain: Optional[str] = None, page: int = 1, per_page: int = 20) -> List[Template]:
        params: Dict[str, Any] = {"page": page, "per_page": per_page}
        if domain:
            params["domain"] = domain
        r = self._request("GET", "/api/v1/templates", params=params)
        r.raise_for_status()
        payload = r.json()
        data = payload if isinstance(payload, list) else payload.get("templates") or payload.get("data") or []
        items: List[Template] = []
        for t in data:
            items.append(Template(id=t.get("id"), name=t["name"], version=t.get("version") or "0.0.0", domain=t.get("domain")))
        return items

    def get_template(self, template_id: str) -> Template:
        r = self._request("GET", f"/api/v1/templates/{template_id}")
        r.raise_for_status()
        raw = r.json()
        t = raw.get("template") if isinstance(raw, dict) and raw.get("template") else raw
        return Template(id=t.get("id"), name=t["name"], version=t.get("version") or "0.0.0", domain=t.get("domain"))

    def get_quotas(self) -> Dict[str, Any]:
        r = self._request("GET", "/api/v1/quotas")
        r.raise_for_status()
        return r.json()

    def get_attestation(self, evaluation_id: str) -> Dict[str, Any]:
        r = self._request("GET", f"/api/v1/attestations/{evaluation_id}")
        r.raise_for_status()
        return r.json()

    # ---- Advanced endpoints: analytics, algorithms, benchmarks, safety, admin ----

    def get_evaluation_analytics(self, timeframe: str = "24h") -> Dict[str, Any]:
        r = self._request("GET", "/api/v1/analytics/evaluation-metrics", params={"timeframe": timeframe})
        r.raise_for_status()
        return r.json()

    def get_template_analytics(self, template_id: str, time_range: str = "30d") -> Dict[str, Any]:
        r = self._request("GET", f"/api/v1/templates/{template_id}/analytics", params={"timeRange": time_range})
        r.raise_for_status()
        return r.json()

    def get_org_templates_analytics(self, org_id: Optional[str] = None, time_range: str = "30d") -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/api/v1/organizations/{oid}/templates/analytics", params={"timeRange": time_range})
        r.raise_for_status()
        return r.json()

    def get_algorithm_metrics(self, org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/api/v1/organizations/{oid}/algorithms/metrics")
        r.raise_for_status()
        return r.json()


    def get_safety_metrics(self, org_id: Optional[str] = None, time_range: str = "30d") -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/api/v1/organizations/{oid}/safety/metrics", params={"timeRange": time_range})
        r.raise_for_status()
        return r.json()

    def get_safety_incidents(self, org_id: Optional[str] = None, status: str = "open") -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/api/v1/organizations/{oid}/safety/incidents", params={"status": status})
        r.raise_for_status()
        return r.json()

    def get_compliance_reports(self, org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/api/v1/organizations/{oid}/safety/compliance")
        r.raise_for_status()
        return r.json()

    def get_organization_metrics(self, org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/api/v1/admin/organizations/{oid}/metrics")
        r.raise_for_status()
        return r.json()

    def get_system_health(self) -> Dict[str, Any]:
        r = self._request("GET", "/api/v1/admin/system/health")
        r.raise_for_status()
        return r.json()

    # ---- Federation (federated learning) ----
    #
    # Readmission PRD P2-01: coordinator legs contract for SDK callers while the
    # `federated-learning` capability stays launch-excluded until A-01 — callers
    # receive 410 until admission. Every leg is org-scoped; pass `org_id` or set
    # `org_id` on the client (mismatch returns organization_forbidden).

    def list_federations(self, org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/api/v1/organizations/{oid}/federation/federations")
        r.raise_for_status()
        return r.json()

    def create_federation(self, payload: Dict[str, Any], org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("POST", f"/api/v1/organizations/{oid}/federation/federations", json=payload)
        r.raise_for_status()
        return r.json()

    def invite_participant(self, federation_id: str, payload: Dict[str, Any], org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("POST", f"/api/v1/organizations/{oid}/federation/federations/{federation_id}/participants", json=payload)
        r.raise_for_status()
        return r.json()

    def start_round(self, payload: Dict[str, Any], org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("POST", f"/api/v1/organizations/{oid}/federation/rounds", json=payload)
        r.raise_for_status()
        return r.json()

    def get_round(self, round_id: str, org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/api/v1/organizations/{oid}/federation/rounds/{round_id}")
        r.raise_for_status()
        return r.json()

    def get_privacy_budget(self, federation_id: str, org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/api/v1/organizations/{oid}/federation/privacy-budget", params={"federationId": federation_id})
        r.raise_for_status()
        return r.json()

    def export_audit(self, federation_id: str, org_id: Optional[str] = None) -> Dict[str, Any]:
        oid = org_id or self.org_id
        r = self._request("GET", f"/api/v1/organizations/{oid}/federation/federations/{federation_id}/audit-export")
        r.raise_for_status()
        return r.json()

    # ---- Rewards & Compilation ----



    # ---- Advanced Analytics ----

    def get_template_usage_metrics(self, template_id: str) -> Dict[str, Any]:
        """Get detailed usage metrics for a template."""
        r = self._request("GET", f"/api/v1/templates/{template_id}/usage-metrics")
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

    # ---- RL environments: registry, versions, episodes, exports, baselines, marketplace ----
    #
    # Route contracts (all org-scoped, verified against the route schemas):
    #   GET  /api/v1/environments
    #   GET  /api/environments/{id}
    #   POST /api/environments
    #   GET  /api/versions?orgId&environment
    #   POST /api/versions
    #   GET  /api/environments/{id}/episodes
    #   GET  /api/environments/{id}/episodes/{episode}
    #   POST /api/environments/{id}/exports
    #   GET  /api/environments/{id}/exports
    #   POST /api/environments/{id}/baselines
    #   GET  /api/environments/{id}/baselines
    #   GET  /api/v1/marketplace/environments
    #   POST /api/v1/marketplace/environments
    #   GET  /api/v1/marketplace/environments/{key}/leaderboard

    def list_environments(self) -> List[Dict[str, Any]]:
        """List the caller organization's registered environments."""
        r = self._request("GET", "/api/v1/environments")
        r.raise_for_status()
        payload = r.json()
        data = payload if isinstance(payload, list) else payload.get("data") or payload.get("environments") or []
        return data

    def get_environment(self, environment_id: str) -> Dict[str, Any]:
        r = self._request("GET", f"/api/environments/{environment_id}")
        r.raise_for_status()
        return r.json()

    def create_environment(self, **fields: Any) -> Dict[str, Any]:
        """Create an environment. Required fields per environmentCreateSchema:
        organization_id, name, prompt_template."""
        r = self._request("POST", "/api/environments", json=fields, headers={}, idempotency=True)
        r.raise_for_status()
        return r.json()

    def list_environment_versions(
        self,
        org_id: Optional[str] = None,
        environment_id: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List published environment versions (org-scoped)."""
        oid = org_id or self.org_id
        if not oid:
            raise ValueError("org_id is required (pass it or configure client org_id)")
        params: Dict[str, Any] = {"orgId": oid}
        if environment_id:
            params["environment"] = environment_id
        if sort_by:
            params["sortBy"] = sort_by
        r = self._request("GET", "/api/versions", params=params)
        r.raise_for_status()
        return r.json()

    def publish_environment_version(
        self,
        org_id: str,
        environment_id: str,
        version: str,
        name: str,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        is_stable: Optional[bool] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Publish a new immutable, content-addressed version (createVersionSchema)."""
        payload: Dict[str, Any] = {
            "orgId": org_id,
            "environmentId": environment_id,
            "version": version,
            "name": name,
        }
        if description is not None:
            payload["description"] = description
        if config is not None:
            payload["config"] = config
        if is_stable is not None:
            payload["isStable"] = is_stable
        if tags is not None:
            payload["tags"] = tags
        r = self._request("POST", "/api/versions", json=payload, headers={}, idempotency=True)
        r.raise_for_status()
        return r.json()

    def list_environment_episodes(
        self,
        environment_id: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List episodes for an environment (cursor-paginated)."""
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        r = self._request(
            "GET",
            f"/api/environments/{environment_id}/episodes",
            params=params or None,
        )
        r.raise_for_status()
        return r.json()

    def get_environment_episode(self, environment_id: str, episode_id: str) -> Dict[str, Any]:
        r = self._request("GET", f"/api/environments/{environment_id}/episodes/{episode_id}")
        r.raise_for_status()
        return r.json()

    def create_environment_export(
        self,
        environment_id: str,
        version_id: str,
        format: str,
        purpose: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an export package (harbor|reward_jsonl|openenv|verifiers)."""
        payload: Dict[str, Any] = {"versionId": version_id, "format": format}
        if purpose is not None:
            payload["purpose"] = purpose
        r = self._request(
            "POST",
            f"/api/environments/{environment_id}/exports",
            json=payload,
            headers={},
            idempotency=True,
        )
        r.raise_for_status()
        return r.json()

    def list_environment_exports(self, environment_id: str) -> List[Dict[str, Any]]:
        r = self._request("GET", f"/api/environments/{environment_id}/exports")
        r.raise_for_status()
        payload = r.json()
        data = payload if isinstance(payload, list) else payload.get("exports") or []
        return data

    def run_environment_baseline(
        self,
        environment_id: str,
        environment_version_id: str,
        task_instance_ids: Optional[List[str]] = None,
        seed: Optional[str] = None,
        budget_cents: Optional[int] = None,
        tool_call_budget: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Enqueue a baseline run on the remote sandbox pool (RunBaselineSchema)."""
        payload: Dict[str, Any] = {"environmentVersionId": environment_version_id}
        if task_instance_ids is not None:
            payload["taskInstanceIds"] = task_instance_ids
        if seed is not None:
            payload["seed"] = seed
        if budget_cents is not None:
            payload["budgetCents"] = budget_cents
        if tool_call_budget is not None:
            payload["toolCallBudget"] = tool_call_budget
        r = self._request(
            "POST",
            f"/api/environments/{environment_id}/baselines",
            json=payload,
            headers={},
            idempotency=True,
        )
        r.raise_for_status()
        return r.json()

    def list_environment_baselines(
        self,
        environment_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        params = {"limit": limit} if limit is not None else None
        r = self._request("GET", f"/api/environments/{environment_id}/baselines", params=params)
        r.raise_for_status()
        payload = r.json()
        data = payload if isinstance(payload, list) else payload.get("baselines") or []
        return data

    def list_marketplace_environments(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        pricing: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List marketplace environment listings visible to the caller's org."""
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if category:
            params["category"] = category
        if difficulty:
            params["difficulty"] = difficulty
        if pricing:
            params["pricing"] = pricing
        if search:
            params["search"] = search
        r = self._request(
            "GET",
            "/api/v1/marketplace/environments",
            params=params or None,
        )
        r.raise_for_status()
        payload = r.json()
        if isinstance(payload, list):
            return payload
        return payload.get("environments") or payload.get("data") or payload.get("items") or []

    def submit_marketplace_environment(
        self,
        name: str,
        description: str,
        category: str,
        difficulty: str,
        pricing: str,
        price_per_use: float,
        task_count: int,
        tags: Optional[List[str]] = None,
        creator_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit an environment listing for marketplace review
        (EnvironmentSubmissionSchema)."""
        payload: Dict[str, Any] = {
            "name": name,
            "description": description,
            "category": category,
            "difficulty": difficulty,
            "pricing": pricing,
            "pricePerUse": price_per_use,
            "taskCount": task_count,
        }
        if tags is not None:
            payload["tags"] = tags
        if creator_id is not None:
            payload["creatorId"] = creator_id
        r = self._request(
            "POST",
            "/api/v1/marketplace/environments",
            json=payload,
            headers={},
            idempotency=True,
        )
        r.raise_for_status()
        return r.json()

    def marketplace_environment_leaderboard(self, environment_key: str) -> Dict[str, Any]:
        """Get the sealed leaderboard for a marketplace environment."""
        r = self._request(
            "GET",
            f"/api/v1/marketplace/environments/{environment_key}/leaderboard",
        )
        r.raise_for_status()
        return r.json()


    # ---- A1 Benchmarks, Certification and Leaderboards ----

    def list_benchmarks(self) -> List[Dict[str, Any]]:
        """List approved public benchmark suites."""
        r = self._request("GET", "/api/v1/benchmarks")
        r.raise_for_status()
        data = r.json()
        return data.get("benchmarks") or data.get("data") or []

    def get_benchmark(self, benchmark_id: str) -> Dict[str, Any]:
        """Fetch one published benchmark suite."""
        r = self._request("GET", f"/api/v1/benchmarks/{benchmark_id}")
        r.raise_for_status()
        data = r.json()
        return data.get("benchmark") or data.get("data") or data

    def get_leaderboard(self, benchmark_id: str) -> List[Dict[str, Any]]:
        """Published leaderboard rows for a suite (snapshots only)."""
        r = self._request("GET", f"/api/v1/leaderboard/{benchmark_id}")
        r.raise_for_status()
        data = r.json()
        return data.get("leaderboard") or data.get("entries") or data.get("data") or []

    def submit_benchmark_evaluation(
        self,
        model_id: str,
        environment_id: Optional[str] = None,
        benchmark_id: Optional[str] = None,
        task_ids: Optional[List[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a model for a benchmark evaluation (A1 customer credential)."""
        body: Dict[str, Any] = {"modelId": model_id}
        if environment_id:
            body["environmentId"] = environment_id
        if benchmark_id:
            body["benchmarkId"] = benchmark_id
        if task_ids:
            body["taskIds"] = task_ids
        headers = {"X-Idempotency-Key": idempotency_key} if idempotency_key else None
        r = self._request(
            "POST",
            "/api/v1/benchmark-evaluations",
            json=body,
            headers=headers,
            idempotency=idempotency_key is None,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("evaluation") or data.get("data") or data

    def get_benchmark_evaluation(self, evaluation_id: str) -> Dict[str, Any]:
        """Status of a submitted benchmark evaluation (org-scoped)."""
        r = self._request("GET", f"/api/v1/benchmark-evaluations/{evaluation_id}")
        r.raise_for_status()
        data = r.json()
        return data.get("evaluation") or data.get("data") or data

    def get_benchmark_review_protocol(self) -> Dict[str, Any]:
        """Human-review protocol: rubric, severities, configured rate."""
        r = self._request("GET", "/api/v1/benchmarks/reviews")
        r.raise_for_status()
        return r.json()

    def get_model_certification(self, model_id: str) -> Dict[str, Any]:
        """Certification decision for a model."""
        r = self._request("GET", f"/api/v1/certification/{model_id}")
        r.raise_for_status()
        data = r.json()
        return data.get("certification") or data.get("data") or data

    def get_model_certification_detail(self, model_id: str) -> Dict[str, Any]:
        """Detailed certification record for a model."""
        r = self._request("GET", f"/api/v1/models/{model_id}/certification")
        r.raise_for_status()
        return r.json()

    def run_regression(
        self,
        model_id: str,
        baseline_model_id: str,
        benchmark_id: Optional[str] = None,
        environment_id: Optional[str] = None,
        task_ids: Optional[List[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request a regression replay against a baseline model."""
        body: Dict[str, Any] = {
            "modelId": model_id,
            "baselineModelId": baseline_model_id,
        }
        if benchmark_id:
            body["benchmarkId"] = benchmark_id
        if environment_id:
            body["environmentId"] = environment_id
        if task_ids:
            body["taskIds"] = task_ids
        headers = {"X-Idempotency-Key": idempotency_key} if idempotency_key else None
        r = self._request(
            "POST",
            "/api/v1/regression",
            json=body,
            headers=headers,
            idempotency=idempotency_key is None,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("regression") or data.get("replay") or data.get("data") or data

    def get_regression(self, replay_id: str) -> Dict[str, Any]:
        """Poll a regression replay result."""
        r = self._request("GET", f"/api/v1/regression/{replay_id}")
        r.raise_for_status()
        data = r.json()
        return data.get("regression") or data.get("replay") or data.get("data") or data

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

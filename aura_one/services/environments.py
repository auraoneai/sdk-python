"""Environments (RL registry + marketplace) service for AuraOne SDK."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..types import RequestConfig
from ..utils import HttpClientProtocol


def _items(response: Any, *keys: str) -> List[Dict[str, Any]]:
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        for key in keys:
            value = response.get(key)
            if isinstance(value, list):
                return value
    return []


class EnvironmentsService:
    """Synchronous environments service.

    Route contracts (all org-scoped):
      GET  /api/v1/environments
      GET  /api/environments/{id}
      POST /api/environments
      GET  /api/versions?orgId&environment
      POST /api/versions
      GET  /api/environments/{id}/episodes
      GET  /api/environments/{id}/episodes/{episode}
      POST /api/environments/{id}/exports
      GET  /api/environments/{id}/exports
      POST /api/environments/{id}/baselines
      GET  /api/environments/{id}/baselines
      GET  /api/v1/marketplace/environments
      POST /api/v1/marketplace/environments
      GET  /api/v1/marketplace/environments/{key}/leaderboard
    """

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def list(self, request_config: Optional[RequestConfig] = None) -> List[Dict[str, Any]]:
        """List the caller organization's registered environments."""
        response = self.http_client.get("/api/v1/environments", config=request_config)
        return _items(response, "data", "environments")

    def get(self, environment_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return self.http_client.get(f"/api/environments/{environment_id}", config=request_config)

    def create(
        self,
        organization_id: str,
        name: str,
        prompt_template: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        input_schema: Optional[Any] = None,
        output_schema: Optional[Any] = None,
        evaluation_criteria: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        settings: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Create a new environment (environmentCreateSchema)."""
        payload: Dict[str, Any] = {
            "organization_id": organization_id,
            "name": name,
            "prompt_template": prompt_template,
        }
        for key, value in {
            "description": description,
            "category": category,
            "status": status,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "evaluation_criteria": evaluation_criteria,
            "tags": tags,
            "settings": settings,
            "metadata": metadata,
            "version": version,
        }.items():
            if value is not None:
                payload[key] = value
        return self.http_client.post("/api/environments", data=payload, config=request_config)

    def list_versions(
        self,
        org_id: str,
        environment_id: Optional[str] = None,
        sort_by: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """List published versions (org-scoped)."""
        params: Dict[str, Any] = {"orgId": org_id}
        if environment_id:
            params["environment"] = environment_id
        if sort_by:
            params["sortBy"] = sort_by
        return self.http_client.get("/api/versions", params=params, config=request_config)

    def publish_version(
        self,
        org_id: str,
        environment_id: str,
        version: str,
        name: str,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        is_stable: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        request_config: Optional[RequestConfig] = None,
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
        return self.http_client.post("/api/versions", data=payload, config=request_config)

    def list_episodes(
        self,
        environment_id: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """List episodes for an environment (cursor-paginated)."""
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        return self.http_client.get(
            f"/api/environments/{environment_id}/episodes",
            params=params or None,
            config=request_config,
        )

    def get_episode(
        self,
        environment_id: str,
        episode_id: str,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return self.http_client.get(
            f"/api/environments/{environment_id}/episodes/{episode_id}",
            config=request_config,
        )

    def create_export(
        self,
        environment_id: str,
        version_id: str,
        format: str,
        purpose: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Create an export package (harbor|reward_jsonl|openenv|verifiers)."""
        payload: Dict[str, Any] = {"versionId": version_id, "format": format}
        if purpose is not None:
            payload["purpose"] = purpose
        return self.http_client.post(
            f"/api/environments/{environment_id}/exports",
            data=payload,
            config=request_config,
        )

    def list_exports(
        self,
        environment_id: str,
        request_config: Optional[RequestConfig] = None,
    ) -> List[Dict[str, Any]]:
        response = self.http_client.get(
            f"/api/environments/{environment_id}/exports",
            config=request_config,
        )
        return _items(response, "exports")

    def run_baseline(
        self,
        environment_id: str,
        environment_version_id: str,
        task_instance_ids: Optional[List[str]] = None,
        seed: Optional[str] = None,
        budget_cents: Optional[int] = None,
        tool_call_budget: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Enqueue a baseline run on the remote sandbox pool."""
        payload: Dict[str, Any] = {"environmentVersionId": environment_version_id}
        if task_instance_ids is not None:
            payload["taskInstanceIds"] = task_instance_ids
        if seed is not None:
            payload["seed"] = seed
        if budget_cents is not None:
            payload["budgetCents"] = budget_cents
        if tool_call_budget is not None:
            payload["toolCallBudget"] = tool_call_budget
        return self.http_client.post(
            f"/api/environments/{environment_id}/baselines",
            data=payload,
            config=request_config,
        )

    def list_baselines(
        self,
        environment_id: str,
        limit: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> List[Dict[str, Any]]:
        params = {"limit": limit} if limit is not None else None
        response = self.http_client.get(
            f"/api/environments/{environment_id}/baselines",
            params=params,
            config=request_config,
        )
        return _items(response, "baselines")

    def list_marketplace(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        pricing: Optional[str] = None,
        search: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
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
        response = self.http_client.get(
            "/api/v1/marketplace/environments",
            params=params or None,
            config=request_config,
        )
        return _items(response, "environments", "data", "items")

    def submit_marketplace_listing(
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
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Submit an environment listing for marketplace review."""
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
        return self.http_client.post(
            "/api/v1/marketplace/environments",
            data=payload,
            config=request_config,
        )

    def marketplace_leaderboard(
        self,
        environment_key: str,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Get the sealed leaderboard for a marketplace environment."""
        return self.http_client.get(
            f"/api/v1/marketplace/environments/{environment_key}/leaderboard",
            config=request_config,
        )


class AsyncEnvironmentsService:
    """Asynchronous environments service (same contracts as the sync service)."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def list(self, request_config: Optional[RequestConfig] = None) -> List[Dict[str, Any]]:
        response = await self.http_client.get("/api/v1/environments", config=request_config)
        return _items(response, "data", "environments")

    async def get(self, environment_id: str, request_config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self.http_client.get(f"/api/environments/{environment_id}", config=request_config)

    async def create(
        self,
        organization_id: str,
        name: str,
        prompt_template: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        input_schema: Optional[Any] = None,
        output_schema: Optional[Any] = None,
        evaluation_criteria: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
        settings: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "organization_id": organization_id,
            "name": name,
            "prompt_template": prompt_template,
        }
        for key, value in {
            "description": description,
            "category": category,
            "status": status,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "evaluation_criteria": evaluation_criteria,
            "tags": tags,
            "settings": settings,
            "metadata": metadata,
            "version": version,
        }.items():
            if value is not None:
                payload[key] = value
        return await self.http_client.post("/api/environments", data=payload, config=request_config)

    async def list_versions(
        self,
        org_id: str,
        environment_id: Optional[str] = None,
        sort_by: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"orgId": org_id}
        if environment_id:
            params["environment"] = environment_id
        if sort_by:
            params["sortBy"] = sort_by
        return await self.http_client.get("/api/versions", params=params, config=request_config)

    async def publish_version(
        self,
        org_id: str,
        environment_id: str,
        version: str,
        name: str,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        is_stable: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
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
        return await self.http_client.post("/api/versions", data=payload, config=request_config)

    async def list_episodes(
        self,
        environment_id: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        return await self.http_client.get(
            f"/api/environments/{environment_id}/episodes",
            params=params or None,
            config=request_config,
        )

    async def get_episode(
        self,
        environment_id: str,
        episode_id: str,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.get(
            f"/api/environments/{environment_id}/episodes/{episode_id}",
            config=request_config,
        )

    async def create_export(
        self,
        environment_id: str,
        version_id: str,
        format: str,
        purpose: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"versionId": version_id, "format": format}
        if purpose is not None:
            payload["purpose"] = purpose
        return await self.http_client.post(
            f"/api/environments/{environment_id}/exports",
            data=payload,
            config=request_config,
        )

    async def list_exports(
        self,
        environment_id: str,
        request_config: Optional[RequestConfig] = None,
    ) -> List[Dict[str, Any]]:
        response = await self.http_client.get(
            f"/api/environments/{environment_id}/exports",
            config=request_config,
        )
        return _items(response, "exports")

    async def run_baseline(
        self,
        environment_id: str,
        environment_version_id: str,
        task_instance_ids: Optional[List[str]] = None,
        seed: Optional[str] = None,
        budget_cents: Optional[int] = None,
        tool_call_budget: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"environmentVersionId": environment_version_id}
        if task_instance_ids is not None:
            payload["taskInstanceIds"] = task_instance_ids
        if seed is not None:
            payload["seed"] = seed
        if budget_cents is not None:
            payload["budgetCents"] = budget_cents
        if tool_call_budget is not None:
            payload["toolCallBudget"] = tool_call_budget
        return await self.http_client.post(
            f"/api/environments/{environment_id}/baselines",
            data=payload,
            config=request_config,
        )

    async def list_baselines(
        self,
        environment_id: str,
        limit: Optional[int] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> List[Dict[str, Any]]:
        params = {"limit": limit} if limit is not None else None
        response = await self.http_client.get(
            f"/api/environments/{environment_id}/baselines",
            params=params,
            config=request_config,
        )
        return _items(response, "baselines")

    async def list_marketplace(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        pricing: Optional[str] = None,
        search: Optional[str] = None,
        request_config: Optional[RequestConfig] = None,
    ) -> List[Dict[str, Any]]:
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
        response = await self.http_client.get(
            "/api/v1/marketplace/environments",
            params=params or None,
            config=request_config,
        )
        return _items(response, "environments", "data", "items")

    async def submit_marketplace_listing(
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
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
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
        return await self.http_client.post(
            "/api/v1/marketplace/environments",
            data=payload,
            config=request_config,
        )

    async def marketplace_leaderboard(
        self,
        environment_key: str,
        request_config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self.http_client.get(
            f"/api/v1/marketplace/environments/{environment_key}/leaderboard",
            config=request_config,
        )

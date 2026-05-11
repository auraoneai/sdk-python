"""Robotics service for AuraOne SDK."""

import asyncio
import time
from typing import Any, AsyncIterator, Callable, Dict, Iterable, Optional, Sequence, Union

from ..exceptions import AuraOneError, NetworkError, RateLimitError, ServerError, TimeoutError
from ..types import RequestConfig

_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
PUBLIC_EXPORT_FORMATS = ("RLDS", "OPENX", "HDF5", "BVH", "JSON")
INTERNAL_SERIALIZER_FORMATS = ("MCAP", "ROSBAG", "PARQUET")


class RoboticsService:
    """Synchronous client for AuraOne Robotics API endpoints."""

    def __init__(self, http_client: Any) -> None:
        self._http = http_client

    def _resolve_retries(self, config: Optional[RequestConfig]) -> int:
        if config and config.max_retries is not None:
            return max(0, config.max_retries)
        return 2

    def _is_retryable_error(self, error: Exception) -> bool:
        if isinstance(error, (NetworkError, TimeoutError, RateLimitError, ServerError)):
            return True

        if isinstance(error, AuraOneError):
            status_code = getattr(error, "status_code", None)
            if isinstance(status_code, int) and status_code in _RETRYABLE_STATUS_CODES:
                return True

        return False

    def _retry_delay_seconds(self, attempt: int) -> float:
        return min(0.5 * (2 ** attempt), 8.0)

    def _resolve_org_id(
        self,
        org_id: Optional[str],
        config: Optional[RequestConfig],
    ) -> str:
        if org_id:
            return org_id

        headers = (config.headers if config else None) or {}
        for key in ("x-organization-id", "X-Organization-Id", "x-org-id", "X-Org-Id"):
            header_value = headers.get(key)
            if isinstance(header_value, str) and header_value.strip():
                return header_value

        raise AuraOneError(
            "org_id is required for robotics workforce operations"
        )

    def _with_retries(
        self,
        call: Callable[[], Dict[str, Any]],
        retries: int,
    ) -> Dict[str, Any]:
        last_error: Optional[Exception] = None

        for attempt in range(retries + 1):
            try:
                return call()
            except Exception as exc:  # pragma: no cover - covered by retry tests
                last_error = exc
                if attempt >= retries or not self._is_retryable_error(exc):
                    raise
                time.sleep(self._retry_delay_seconds(attempt))

        if last_error:
            raise last_error

        raise AuraOneError("Robotics request failed")

    # -- Datasets --

    def get_stats(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Get canonical robotics lab statistics."""
        return self._with_retries(
            lambda: self._http.get("/api/v1/labs/robotics/stats", config=config),
            retries=self._resolve_retries(config),
        )

    def list_datasets(
        self,
        page: int = 1,
        limit: int = 20,
        lab_id: Optional[str] = None,
        data_mode: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """List robotics datasets with pagination controls."""
        safe_page = max(1, page)
        safe_limit = min(100, max(1, limit))
        params: Dict[str, Any] = {
            "page": safe_page,
            "limit": safe_limit,
        }

        if lab_id:
            params["labId"] = lab_id
        if data_mode:
            params["dataMode"] = data_mode

        response = self._with_retries(
            lambda: self._http.get("/api/v1/robotics/datasets", params=params, config=config),
            retries=self._resolve_retries(config),
        )

        total = int(response.get("total", len(response.get("datasets", []))))
        response["pagination"] = {
            "page": safe_page,
            "limit": safe_limit,
            "total": total,
            "hasNext": safe_page * safe_limit < total,
            "hasPrev": safe_page > 1,
        }
        return response

    def iter_datasets(
        self,
        limit: int = 100,
        lab_id: Optional[str] = None,
        data_mode: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Iterable[Dict[str, Any]]:
        """Iterate all dataset records using server-side pagination."""
        page = 1

        while True:
            batch = self.list_datasets(
                page=page,
                limit=limit,
                lab_id=lab_id,
                data_mode=data_mode,
                config=config,
            )

            datasets = batch.get("datasets", [])
            for dataset in datasets:
                yield dataset

            pagination = batch.get("pagination") or {}
            if not pagination.get("hasNext"):
                break
            page += 1

    def list_all_datasets(
        self,
        limit: int = 100,
        lab_id: Optional[str] = None,
        data_mode: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Fetch every available dataset page and return a flattened payload."""
        datasets = list(
            self.iter_datasets(
                limit=limit,
                lab_id=lab_id,
                data_mode=data_mode,
                config=config,
            )
        )
        return {
            "datasets": datasets,
            "total": len(datasets),
            "pagination": {
                "page": 1,
                "limit": max(1, limit),
                "total": len(datasets),
                "hasNext": False,
                "hasPrev": False,
            },
        }

    def create_dataset(
        self,
        name: str,
        data_mode: str,
        robot_platform: str,
        task_category: str,
        description: Optional[str] = None,
        lab_id: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Create a robotics dataset."""
        payload: Dict[str, Any] = {
            "name": name,
            "dataMode": data_mode,
            "robotPlatform": robot_platform,
            "taskCategory": task_category,
        }
        if description is not None:
            payload["description"] = description
        if lab_id:
            payload["labId"] = lab_id

        return self._with_retries(
            lambda: self._http.post("/api/v1/robotics/datasets", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    def ingest_data(
        self,
        dataset_id: str,
        payload: Dict[str, Any],
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Ingest trajectory data into a robotics dataset."""
        return self._with_retries(
            lambda: self._http.post(
                f"/api/v1/robotics/datasets/{dataset_id}/ingest",
                data=payload,
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    # -- Simulators --

    def list_simulators(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """List simulator engines and recent runs."""
        return self._with_retries(
            lambda: self._http.get("/api/v1/robotics/simulators", config=config),
            retries=self._resolve_retries(config),
        )

    def create_simulation(
        self,
        engine: str,
        scene_name: str,
        task_description: str,
        trajectory_count: int,
        dataset_id: str,
        seed: Optional[int] = None,
        max_steps: Optional[int] = None,
        simulation_config: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Create a simulator run."""
        payload: Dict[str, Any] = {
            "engine": engine,
            "sceneName": scene_name,
            "taskDescription": task_description,
            "trajectoryCount": trajectory_count,
            "datasetId": dataset_id,
        }
        if seed is not None:
            payload["seed"] = seed
        if max_steps is not None:
            payload["maxSteps"] = max_steps
        if simulation_config is not None:
            payload["config"] = simulation_config

        return self._with_retries(
            lambda: self._http.post("/api/v1/robotics/simulators", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    # -- Teleoperation --

    def list_sessions(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """List teleoperation sessions."""
        return self._with_retries(
            lambda: self._http.get("/api/v1/robotics/teleoperation", config=config),
            retries=self._resolve_retries(config),
        )

    def create_session(
        self,
        dataset_name: str,
        control_mode: str,
        worker_id: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Create a teleoperation session."""
        payload: Dict[str, Any] = {
            "datasetName": dataset_name,
            "controlMode": control_mode,
        }
        if worker_id:
            payload["workerId"] = worker_id

        return self._with_retries(
            lambda: self._http.post("/api/v1/robotics/teleoperation", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    def send_telemetry(
        self,
        session_id: str,
        events: Union[Dict[str, Any], Sequence[Dict[str, Any]]],
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Ingest teleoperation telemetry events for a session."""
        if isinstance(events, Sequence) and not isinstance(events, dict):
            payload: Dict[str, Any] = {"events": list(events)}
        else:
            payload = events if isinstance(events, dict) else {"events": []}

        return self._with_retries(
            lambda: self._http.post(
                f"/api/v1/robotics/teleoperation/{session_id}/events",
                data=payload,
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    def finalize_session(
        self,
        session_id: str,
        task_description: str,
        task_success: bool,
        status: Optional[str] = None,
        video_url: Optional[str] = None,
        sensor_data_url: Optional[str] = None,
        command_data_url: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Finalize a teleoperation session."""
        payload: Dict[str, Any] = {
            "taskDescription": task_description,
            "taskSuccess": task_success,
        }
        if status:
            payload["status"] = status
        if video_url:
            payload["videoUrl"] = video_url
        if sensor_data_url:
            payload["sensorDataUrl"] = sensor_data_url
        if command_data_url:
            payload["commandDataUrl"] = command_data_url
        if metadata_json is not None:
            payload["metadataJson"] = metadata_json

        return self._with_retries(
            lambda: self._http.post(
                f"/api/v1/robotics/teleoperation/{session_id}/finalize",
                data=payload,
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    # -- Exports --

    def create_export(
        self,
        dataset_id: str,
        export_format: str = "JSON",
        max_trajectories: Optional[int] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Create a robotics dataset export job or synchronous export."""
        payload: Dict[str, Any] = {
            "datasetId": dataset_id,
            "format": export_format,
        }
        if max_trajectories is not None:
            payload["maxTrajectories"] = max_trajectories

        return self._with_retries(
            lambda: self._http.post("/api/v1/robotics/exports", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    def get_export(
        self,
        dataset_id: Optional[str] = None,
        export_format: str = "JSON",
        download_token: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Any:
        """Download a robotics export artifact."""
        params: Dict[str, Any] = {}
        if dataset_id:
            params["datasetId"] = dataset_id
        if export_format:
            params["format"] = export_format
        if download_token:
            params["downloadToken"] = download_token

        return self._with_retries(
            lambda: self._http.get("/api/v1/robotics/exports", params=params, config=config),
            retries=self._resolve_retries(config),
        )

    def get_export_status(
        self,
        job_id: str,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Poll status for an async robotics export job."""
        return self._with_retries(
            lambda: self._http.get(
                "/api/v1/robotics/exports/status",
                params={"jobId": job_id},
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    def get_settings(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Get robotics settings and provider readiness checks."""
        return self._with_retries(
            lambda: self._http.get("/api/v1/robotics/settings", config=config),
            retries=self._resolve_retries(config),
        )

    # -- Quality --

    def get_quality_metrics(
        self,
        dataset_id: Optional[str] = None,
        drift: bool = False,
        drift_window: Optional[int] = None,
        baseline_window: Optional[int] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Get robotics quality metrics and optional drift details."""
        params: Dict[str, Any] = {}
        if dataset_id:
            params["datasetId"] = dataset_id
        if drift:
            params["drift"] = "true"
        if drift_window is not None:
            params["driftWindow"] = drift_window
        if baseline_window is not None:
            params["baselineWindow"] = baseline_window

        return self._with_retries(
            lambda: self._http.get("/api/v1/robotics/quality", params=params, config=config),
            retries=self._resolve_retries(config),
        )

    # -- Safety --

    def get_safety_metrics(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Get robotics safety snapshot and compliance summary."""
        return self._with_retries(
            lambda: self._http.get("/api/v1/robotics/safety", config=config),
            retries=self._resolve_retries(config),
        )

    def issue_certification(
        self,
        worker_id: str,
        certification_level: str,
        robot_platforms: Sequence[str],
        exam_score: float,
        practical_score: float,
        expires_at: str,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Issue or renew a worker robotics certification."""
        payload = {
            "workerId": worker_id,
            "certificationLevel": certification_level,
            "robotPlatforms": list(robot_platforms),
            "examScore": exam_score,
            "practicalScore": practical_score,
            "expiresAt": expires_at,
        }

        return self._with_retries(
            lambda: self._http.post("/api/v1/robotics/safety", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    # -- Workforce / Throughput --

    def list_workforce(
        self,
        org_id: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """List workforce operators and throughput snapshot."""
        resolved_org_id = self._resolve_org_id(org_id, config)
        return self._with_retries(
            lambda: self._http.get(
                "/api/v1/robotics/workforce",
                params={"orgId": resolved_org_id},
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    def assign_operator(
        self,
        operator_id: str,
        task_type: str,
        priority: str = "normal",
        dataset_id: Optional[str] = None,
        org_id: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Assign a robotics task to an operator."""
        resolved_org_id = self._resolve_org_id(org_id, config)
        payload: Dict[str, Any] = {
            "action": "assign",
            "orgId": resolved_org_id,
            "operatorId": operator_id,
            "taskType": task_type,
            "priority": priority,
        }
        if dataset_id:
            payload["datasetId"] = dataset_id

        return self._with_retries(
            lambda: self._http.post("/api/v1/robotics/workforce", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    def batch_assign(
        self,
        tasks: Sequence[Dict[str, Any]],
        org_id: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Assign multiple tasks in one request."""
        resolved_org_id = self._resolve_org_id(org_id, config)
        return self._with_retries(
            lambda: self._http.post(
                "/api/v1/robotics/workforce",
                data={
                    "action": "batch_assign",
                    "orgId": resolved_org_id,
                    "tasks": list(tasks),
                },
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    def get_throughput_slos(
        self,
        tier: str = "professional",
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Get throughput SLO evaluations."""
        return self._with_retries(
            lambda: self._http.get(
                "/api/v1/robotics/throughput",
                params={"tier": tier},
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    def record_slo_measurement(
        self,
        slo_id: str,
        measurements: Sequence[Dict[str, Any]],
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        """Record throughput SLO measurements."""
        payload = {
            "sloId": slo_id,
            "measurements": list(measurements),
        }
        return self._with_retries(
            lambda: self._http.post("/api/v1/robotics/throughput", data=payload, config=config),
            retries=self._resolve_retries(config),
        )


class AsyncRoboticsService:
    """Async client for AuraOne Robotics API endpoints."""

    def __init__(self, http_client: Any) -> None:
        self._http = http_client

    def _resolve_retries(self, config: Optional[RequestConfig]) -> int:
        if config and config.max_retries is not None:
            return max(0, config.max_retries)
        return 2

    def _is_retryable_error(self, error: Exception) -> bool:
        if isinstance(error, (NetworkError, TimeoutError, RateLimitError, ServerError)):
            return True

        if isinstance(error, AuraOneError):
            status_code = getattr(error, "status_code", None)
            if isinstance(status_code, int) and status_code in _RETRYABLE_STATUS_CODES:
                return True

        return False

    def _retry_delay_seconds(self, attempt: int) -> float:
        return min(0.5 * (2 ** attempt), 8.0)

    def _resolve_org_id(
        self,
        org_id: Optional[str],
        config: Optional[RequestConfig],
    ) -> str:
        if org_id:
            return org_id

        headers = (config.headers if config else None) or {}
        for key in ("x-organization-id", "X-Organization-Id", "x-org-id", "X-Org-Id"):
            header_value = headers.get(key)
            if isinstance(header_value, str) and header_value.strip():
                return header_value

        raise AuraOneError(
            "org_id is required for robotics workforce operations"
        )

    async def _with_retries(
        self,
        call: Callable[[], Any],
        retries: int,
    ) -> Dict[str, Any]:
        last_error: Optional[Exception] = None

        for attempt in range(retries + 1):
            try:
                return await call()
            except Exception as exc:  # pragma: no cover - covered by retry tests
                last_error = exc
                if attempt >= retries or not self._is_retryable_error(exc):
                    raise
                await asyncio.sleep(self._retry_delay_seconds(attempt))

        if last_error:
            raise last_error

        raise AuraOneError("Robotics request failed")

    # -- Datasets --

    async def get_stats(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self._with_retries(
            lambda: self._http.get("/api/v1/labs/robotics/stats", config=config),
            retries=self._resolve_retries(config),
        )

    async def list_datasets(
        self,
        page: int = 1,
        limit: int = 20,
        lab_id: Optional[str] = None,
        data_mode: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        safe_page = max(1, page)
        safe_limit = min(100, max(1, limit))
        params: Dict[str, Any] = {
            "page": safe_page,
            "limit": safe_limit,
        }

        if lab_id:
            params["labId"] = lab_id
        if data_mode:
            params["dataMode"] = data_mode

        response = await self._with_retries(
            lambda: self._http.get("/api/v1/robotics/datasets", params=params, config=config),
            retries=self._resolve_retries(config),
        )

        total = int(response.get("total", len(response.get("datasets", []))))
        response["pagination"] = {
            "page": safe_page,
            "limit": safe_limit,
            "total": total,
            "hasNext": safe_page * safe_limit < total,
            "hasPrev": safe_page > 1,
        }
        return response

    async def iter_datasets(
        self,
        limit: int = 100,
        lab_id: Optional[str] = None,
        data_mode: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        page = 1

        while True:
            batch = await self.list_datasets(
                page=page,
                limit=limit,
                lab_id=lab_id,
                data_mode=data_mode,
                config=config,
            )

            for dataset in batch.get("datasets", []):
                yield dataset

            pagination = batch.get("pagination") or {}
            if not pagination.get("hasNext"):
                break
            page += 1

    async def list_all_datasets(
        self,
        limit: int = 100,
        lab_id: Optional[str] = None,
        data_mode: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        datasets = []
        async for dataset in self.iter_datasets(
            limit=limit,
            lab_id=lab_id,
            data_mode=data_mode,
            config=config,
        ):
            datasets.append(dataset)

        return {
            "datasets": datasets,
            "total": len(datasets),
            "pagination": {
                "page": 1,
                "limit": max(1, limit),
                "total": len(datasets),
                "hasNext": False,
                "hasPrev": False,
            },
        }

    async def create_dataset(
        self,
        name: str,
        data_mode: str,
        robot_platform: str,
        task_category: str,
        description: Optional[str] = None,
        lab_id: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": name,
            "dataMode": data_mode,
            "robotPlatform": robot_platform,
            "taskCategory": task_category,
        }
        if description is not None:
            payload["description"] = description
        if lab_id:
            payload["labId"] = lab_id

        return await self._with_retries(
            lambda: self._http.post("/api/v1/robotics/datasets", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    async def ingest_data(
        self,
        dataset_id: str,
        payload: Dict[str, Any],
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self._with_retries(
            lambda: self._http.post(
                f"/api/v1/robotics/datasets/{dataset_id}/ingest",
                data=payload,
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    # -- Simulators --

    async def list_simulators(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self._with_retries(
            lambda: self._http.get("/api/v1/robotics/simulators", config=config),
            retries=self._resolve_retries(config),
        )

    async def create_simulation(
        self,
        engine: str,
        scene_name: str,
        task_description: str,
        trajectory_count: int,
        dataset_id: str,
        seed: Optional[int] = None,
        max_steps: Optional[int] = None,
        simulation_config: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "engine": engine,
            "sceneName": scene_name,
            "taskDescription": task_description,
            "trajectoryCount": trajectory_count,
            "datasetId": dataset_id,
        }
        if seed is not None:
            payload["seed"] = seed
        if max_steps is not None:
            payload["maxSteps"] = max_steps
        if simulation_config is not None:
            payload["config"] = simulation_config

        return await self._with_retries(
            lambda: self._http.post("/api/v1/robotics/simulators", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    # -- Teleoperation --

    async def list_sessions(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self._with_retries(
            lambda: self._http.get("/api/v1/robotics/teleoperation", config=config),
            retries=self._resolve_retries(config),
        )

    async def create_session(
        self,
        dataset_name: str,
        control_mode: str,
        worker_id: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "datasetName": dataset_name,
            "controlMode": control_mode,
        }
        if worker_id:
            payload["workerId"] = worker_id

        return await self._with_retries(
            lambda: self._http.post("/api/v1/robotics/teleoperation", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    async def send_telemetry(
        self,
        session_id: str,
        events: Union[Dict[str, Any], Sequence[Dict[str, Any]]],
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        if isinstance(events, Sequence) and not isinstance(events, dict):
            payload: Dict[str, Any] = {"events": list(events)}
        else:
            payload = events if isinstance(events, dict) else {"events": []}

        return await self._with_retries(
            lambda: self._http.post(
                f"/api/v1/robotics/teleoperation/{session_id}/events",
                data=payload,
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    async def finalize_session(
        self,
        session_id: str,
        task_description: str,
        task_success: bool,
        status: Optional[str] = None,
        video_url: Optional[str] = None,
        sensor_data_url: Optional[str] = None,
        command_data_url: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "taskDescription": task_description,
            "taskSuccess": task_success,
        }
        if status:
            payload["status"] = status
        if video_url:
            payload["videoUrl"] = video_url
        if sensor_data_url:
            payload["sensorDataUrl"] = sensor_data_url
        if command_data_url:
            payload["commandDataUrl"] = command_data_url
        if metadata_json is not None:
            payload["metadataJson"] = metadata_json

        return await self._with_retries(
            lambda: self._http.post(
                f"/api/v1/robotics/teleoperation/{session_id}/finalize",
                data=payload,
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    # -- Exports --

    async def create_export(
        self,
        dataset_id: str,
        export_format: str = "JSON",
        max_trajectories: Optional[int] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "datasetId": dataset_id,
            "format": export_format,
        }
        if max_trajectories is not None:
            payload["maxTrajectories"] = max_trajectories

        return await self._with_retries(
            lambda: self._http.post("/api/v1/robotics/exports", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    async def get_export(
        self,
        dataset_id: Optional[str] = None,
        export_format: str = "JSON",
        download_token: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Any:
        params: Dict[str, Any] = {}
        if dataset_id:
            params["datasetId"] = dataset_id
        if export_format:
            params["format"] = export_format
        if download_token:
            params["downloadToken"] = download_token

        return await self._with_retries(
            lambda: self._http.get("/api/v1/robotics/exports", params=params, config=config),
            retries=self._resolve_retries(config),
        )

    async def get_export_status(
        self,
        job_id: str,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self._with_retries(
            lambda: self._http.get(
                "/api/v1/robotics/exports/status",
                params={"jobId": job_id},
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    async def get_settings(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self._with_retries(
            lambda: self._http.get("/api/v1/robotics/settings", config=config),
            retries=self._resolve_retries(config),
        )

    # -- Quality --

    async def get_quality_metrics(
        self,
        dataset_id: Optional[str] = None,
        drift: bool = False,
        drift_window: Optional[int] = None,
        baseline_window: Optional[int] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if dataset_id:
            params["datasetId"] = dataset_id
        if drift:
            params["drift"] = "true"
        if drift_window is not None:
            params["driftWindow"] = drift_window
        if baseline_window is not None:
            params["baselineWindow"] = baseline_window

        return await self._with_retries(
            lambda: self._http.get("/api/v1/robotics/quality", params=params, config=config),
            retries=self._resolve_retries(config),
        )

    # -- Safety --

    async def get_safety_metrics(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        return await self._with_retries(
            lambda: self._http.get("/api/v1/robotics/safety", config=config),
            retries=self._resolve_retries(config),
        )

    async def issue_certification(
        self,
        worker_id: str,
        certification_level: str,
        robot_platforms: Sequence[str],
        exam_score: float,
        practical_score: float,
        expires_at: str,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload = {
            "workerId": worker_id,
            "certificationLevel": certification_level,
            "robotPlatforms": list(robot_platforms),
            "examScore": exam_score,
            "practicalScore": practical_score,
            "expiresAt": expires_at,
        }

        return await self._with_retries(
            lambda: self._http.post("/api/v1/robotics/safety", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    # -- Workforce / Throughput --

    async def list_workforce(
        self,
        org_id: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        resolved_org_id = self._resolve_org_id(org_id, config)
        return await self._with_retries(
            lambda: self._http.get(
                "/api/v1/robotics/workforce",
                params={"orgId": resolved_org_id},
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    async def assign_operator(
        self,
        operator_id: str,
        task_type: str,
        priority: str = "normal",
        dataset_id: Optional[str] = None,
        org_id: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        resolved_org_id = self._resolve_org_id(org_id, config)
        payload: Dict[str, Any] = {
            "action": "assign",
            "orgId": resolved_org_id,
            "operatorId": operator_id,
            "taskType": task_type,
            "priority": priority,
        }
        if dataset_id:
            payload["datasetId"] = dataset_id

        return await self._with_retries(
            lambda: self._http.post("/api/v1/robotics/workforce", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

    async def batch_assign(
        self,
        tasks: Sequence[Dict[str, Any]],
        org_id: Optional[str] = None,
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        resolved_org_id = self._resolve_org_id(org_id, config)
        return await self._with_retries(
            lambda: self._http.post(
                "/api/v1/robotics/workforce",
                data={
                    "action": "batch_assign",
                    "orgId": resolved_org_id,
                    "tasks": list(tasks),
                },
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    async def get_throughput_slos(
        self,
        tier: str = "professional",
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        return await self._with_retries(
            lambda: self._http.get(
                "/api/v1/robotics/throughput",
                params={"tier": tier},
                config=config,
            ),
            retries=self._resolve_retries(config),
        )

    async def record_slo_measurement(
        self,
        slo_id: str,
        measurements: Sequence[Dict[str, Any]],
        config: Optional[RequestConfig] = None,
    ) -> Dict[str, Any]:
        payload = {
            "sloId": slo_id,
            "measurements": list(measurements),
        }
        return await self._with_retries(
            lambda: self._http.post("/api/v1/robotics/throughput", data=payload, config=config),
            retries=self._resolve_retries(config),
        )

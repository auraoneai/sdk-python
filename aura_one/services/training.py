"""Training service for AuraOne SDK."""

from typing import Optional, Dict, Any
from ..types import RequestConfig, TrainingExportRequest
from ..utils import HttpClientProtocol


class TrainingService:
    """Synchronous training service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def export_training_data(self, request: TrainingExportRequest, config: Optional[RequestConfig] = None) -> str:
        """Export training data."""
        data = self._serialize_export_request(request)
        return self.http_client.post("/api/training/export", data=data, config=config)

    def export_dpo(self, org_id: str, **kwargs) -> str:
        """Export DPO format training data."""
        request = TrainingExportRequest(org_id=org_id, format="dpo", **kwargs)
        return self.export_training_data(request)

    def _serialize_export_request(self, request: TrainingExportRequest) -> Dict[str, Any]:
        """Serialize export request."""
        data = {
            "orgId": request.org_id,
            "format": request.format.value,
            "includeMetadata": request.include_metadata,
            "minConfidence": request.min_confidence,
            "normalizeScores": request.normalize_scores,
            "validateOutput": request.validate_output,
        }
        if request.sft_format:
            data["sftFormat"] = request.sft_format.value
        return data


class AsyncTrainingService:
    """Asynchronous training service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def export_training_data(self, request: TrainingExportRequest, config: Optional[RequestConfig] = None) -> str:
        """Export training data."""
        data = self._serialize_export_request(request)
        return await self.http_client.post("/api/training/export", data=data, config=config)

    async def export_dpo(self, org_id: str, **kwargs) -> str:
        """Export DPO format training data."""
        request = TrainingExportRequest(org_id=org_id, format="dpo", **kwargs)
        return await self.export_training_data(request)

    def _serialize_export_request(self, request: TrainingExportRequest) -> Dict[str, Any]:
        """Serialize export request."""
        data = {
            "orgId": request.org_id,
            "format": request.format.value,
            "includeMetadata": request.include_metadata,
            "minConfidence": request.min_confidence,
            "normalizeScores": request.normalize_scores,
            "validateOutput": request.validate_output,
        }
        if request.sft_format:
            data["sftFormat"] = request.sft_format.value
        return data
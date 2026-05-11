"""Billing service for AuraOne SDK."""

from typing import Optional, Dict, Any
from ..types import RequestConfig
from ..utils import HttpClientProtocol


class BillingService:
    """Synchronous billing service."""

    def __init__(self, http_client: HttpClientProtocol):
        self.http_client = http_client

    def get_billing_info(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Get billing information."""
        return self.http_client.get("/api/billing", config=config)


class AsyncBillingService:
    """Asynchronous billing service."""

    def __init__(self, http_client):
        self.http_client = http_client

    async def get_billing_info(self, config: Optional[RequestConfig] = None) -> Dict[str, Any]:
        """Get billing information."""
        return await self.http_client.get("/api/billing", config=config)
"""Analytics service for AuraOne SDK."""

from typing import Dict, List, Any, Optional
from datetime import datetime

from ..types import (
    AnalyticsEvent,
    AnalyticsResponse,
    AnalyticsHealthResponse,
    EventCategory,
    RequestConfig,
)
from ..utils import HttpClientProtocol


class AnalyticsService:
    """Synchronous analytics service."""

    def __init__(self, http_client: HttpClientProtocol):
        """Initialize analytics service.

        Args:
            http_client: HTTP client for making requests
        """
        self.http_client = http_client

    def submit_event(
        self,
        event: AnalyticsEvent,
        config: Optional[RequestConfig] = None
    ) -> AnalyticsResponse:
        """Submit a single analytics event.

        Args:
            event: Analytics event to submit
            config: Optional request configuration

        Returns:
            Analytics response with submission status
        """
        event_data = self._serialize_event(event)
        response = self.http_client.post("/api/analytics/events", data=event_data, config=config)
        return AnalyticsResponse(**response)

    def submit_events(
        self,
        events: List[AnalyticsEvent],
        context: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None
    ) -> AnalyticsResponse:
        """Submit multiple analytics events.

        Args:
            events: List of analytics events to submit
            context: Optional context information
            config: Optional request configuration

        Returns:
            Analytics response with submission status
        """
        data = {
            "events": [self._serialize_event(event) for event in events],
            "batch": True,
            "context": context,
        }
        response = self.http_client.post("/api/analytics/events", data=data, config=config)
        return AnalyticsResponse(**response)

    def get_health(self, config: Optional[RequestConfig] = None) -> AnalyticsHealthResponse:
        """Get analytics service health status.

        Args:
            config: Optional request configuration

        Returns:
            Analytics health response
        """
        response = self.http_client.get("/api/analytics/events", config=config)
        return AnalyticsHealthResponse(
            status=response["status"],
            service=response["service"],
            timestamp=datetime.fromisoformat(response["timestamp"]),
            supported_events=response["supported_events"],
        )

    def track_user(
        self,
        event_name: str,
        properties: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        config: Optional[RequestConfig] = None
    ) -> AnalyticsResponse:
        """Track a user event.

        Args:
            event_name: Name of the event
            properties: Event properties
            user_id: User identifier
            config: Optional request configuration

        Returns:
            Analytics response
        """
        event = AnalyticsEvent(
            name=event_name,
            category=EventCategory.USER,
            properties=properties or {},
            user_id=user_id,
            timestamp=datetime.now(),
        )
        return self.submit_event(event, config)

    def track_system(
        self,
        event_name: str,
        properties: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None
    ) -> AnalyticsResponse:
        """Track a system event.

        Args:
            event_name: Name of the event
            properties: Event properties
            config: Optional request configuration

        Returns:
            Analytics response
        """
        event = AnalyticsEvent(
            name=event_name,
            category=EventCategory.SYSTEM,
            properties=properties or {},
            timestamp=datetime.now(),
        )
        return self.submit_event(event, config)

    def track_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None
    ) -> AnalyticsResponse:
        """Track an error event.

        Args:
            error: Exception that occurred
            context: Additional context
            config: Optional request configuration

        Returns:
            Analytics response
        """
        error_data = {
            "message": str(error),
            "type": error.__class__.__name__,
        }

        if hasattr(error, "__traceback__") and error.__traceback__:
            import traceback
            error_data["stack_trace"] = "".join(traceback.format_tb(error.__traceback__))

        properties = {**error_data, **(context or {})}

        event = AnalyticsEvent(
            name="error_occurred",
            category=EventCategory.ERROR,
            properties=properties,
            timestamp=datetime.now(),
        )
        return self.submit_event(event, config)

    def _serialize_event(self, event: AnalyticsEvent) -> Dict[str, Any]:
        """Serialize analytics event for API request."""
        data = {
            "name": event.name,
            "category": event.category.value,
        }

        if event.properties:
            data["properties"] = event.properties

        if event.timestamp:
            data["timestamp"] = event.timestamp.isoformat()

        if event.user_id:
            data["userId"] = event.user_id

        if event.session_id:
            data["sessionId"] = event.session_id

        if event.organization_id:
            data["organizationId"] = event.organization_id

        return data


class AsyncAnalyticsService:
    """Asynchronous analytics service."""

    def __init__(self, http_client):
        """Initialize async analytics service.

        Args:
            http_client: Async HTTP client for making requests
        """
        self.http_client = http_client

    async def submit_event(
        self,
        event: AnalyticsEvent,
        config: Optional[RequestConfig] = None
    ) -> AnalyticsResponse:
        """Submit a single analytics event.

        Args:
            event: Analytics event to submit
            config: Optional request configuration

        Returns:
            Analytics response with submission status
        """
        event_data = self._serialize_event(event)
        response = await self.http_client.post("/api/analytics/events", data=event_data, config=config)
        return AnalyticsResponse(**response)

    async def submit_events(
        self,
        events: List[AnalyticsEvent],
        context: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None
    ) -> AnalyticsResponse:
        """Submit multiple analytics events.

        Args:
            events: List of analytics events to submit
            context: Optional context information
            config: Optional request configuration

        Returns:
            Analytics response with submission status
        """
        data = {
            "events": [self._serialize_event(event) for event in events],
            "batch": True,
            "context": context,
        }
        response = await self.http_client.post("/api/analytics/events", data=data, config=config)
        return AnalyticsResponse(**response)

    async def get_health(self, config: Optional[RequestConfig] = None) -> AnalyticsHealthResponse:
        """Get analytics service health status.

        Args:
            config: Optional request configuration

        Returns:
            Analytics health response
        """
        response = await self.http_client.get("/api/analytics/events", config=config)
        return AnalyticsHealthResponse(
            status=response["status"],
            service=response["service"],
            timestamp=datetime.fromisoformat(response["timestamp"]),
            supported_events=response["supported_events"],
        )

    async def track_user(
        self,
        event_name: str,
        properties: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        config: Optional[RequestConfig] = None
    ) -> AnalyticsResponse:
        """Track a user event.

        Args:
            event_name: Name of the event
            properties: Event properties
            user_id: User identifier
            config: Optional request configuration

        Returns:
            Analytics response
        """
        event = AnalyticsEvent(
            name=event_name,
            category=EventCategory.USER,
            properties=properties or {},
            user_id=user_id,
            timestamp=datetime.now(),
        )
        return await self.submit_event(event, config)

    async def track_system(
        self,
        event_name: str,
        properties: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None
    ) -> AnalyticsResponse:
        """Track a system event.

        Args:
            event_name: Name of the event
            properties: Event properties
            config: Optional request configuration

        Returns:
            Analytics response
        """
        event = AnalyticsEvent(
            name=event_name,
            category=EventCategory.SYSTEM,
            properties=properties or {},
            timestamp=datetime.now(),
        )
        return await self.submit_event(event, config)

    async def track_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        config: Optional[RequestConfig] = None
    ) -> AnalyticsResponse:
        """Track an error event.

        Args:
            error: Exception that occurred
            context: Additional context
            config: Optional request configuration

        Returns:
            Analytics response
        """
        error_data = {
            "message": str(error),
            "type": error.__class__.__name__,
        }

        if hasattr(error, "__traceback__") and error.__traceback__:
            import traceback
            error_data["stack_trace"] = "".join(traceback.format_tb(error.__traceback__))

        properties = {**error_data, **(context or {})}

        event = AnalyticsEvent(
            name="error_occurred",
            category=EventCategory.ERROR,
            properties=properties,
            timestamp=datetime.now(),
        )
        return await self.submit_event(event, config)

    def _serialize_event(self, event: AnalyticsEvent) -> Dict[str, Any]:
        """Serialize analytics event for API request."""
        data = {
            "name": event.name,
            "category": event.category.value,
        }

        if event.properties:
            data["properties"] = event.properties

        if event.timestamp:
            data["timestamp"] = event.timestamp.isoformat()

        if event.user_id:
            data["userId"] = event.user_id

        if event.session_id:
            data["sessionId"] = event.session_id

        if event.organization_id:
            data["organizationId"] = event.organization_id

        return data


__all__ = ["AnalyticsService", "AsyncAnalyticsService"]
"""Type definitions for AuraOne SDK."""

from typing import Dict, List, Optional, Union, Any, Literal
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


# Event categories
class EventCategory(str, Enum):
    """Analytics event categories."""

    USER = "user"
    SYSTEM = "system"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    ERROR = "error"


# Training formats
class TrainingFormat(str, Enum):
    """Training data export formats."""

    DPO = "dpo"
    PPO = "ppo"
    SFT = "sft"
    SPAN = "span"
    TRAJECTORY = "trajectory"


class SFTFormat(str, Enum):
    """SFT format variants."""

    ALPACA = "alpaca"
    SHAREGPT = "sharegpt"
    CUSTOM = "custom"


# Configuration types
@dataclass
class ClientConfig:
    """Client configuration options."""

    api_key: Optional[str] = None
    base_url: str = "https://api.auraone.ai"
    timeout: float = 30.0
    max_retries: int = 3
    rate_limit_retry: bool = True
    debug: bool = False
    user_agent: Optional[str] = None
    organization_id: Optional[str] = None


@dataclass
class RequestConfig:
    """Per-request configuration options."""

    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    headers: Optional[Dict[str, str]] = None


# Authentication types
@dataclass
class APIKey:
    """API key information."""

    id: str
    name: str
    prefix: str
    permissions: List[str]
    is_active: bool
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class CreateAPIKeyRequest:
    """Request to create an API key."""

    name: str
    permissions: List[str]
    expires_at: Optional[datetime] = None


@dataclass
class APIKeyResponse:
    """Response from API key operations."""

    success: bool
    api_key: Optional[str] = None
    message: Optional[str] = None
    warning: Optional[str] = None


@dataclass
class ListAPIKeysResponse:
    """Response from listing API keys."""

    success: bool
    api_keys: List[APIKey]
    available_permissions: List[str]
    stats: Optional[Dict[str, Any]] = None


# Analytics types
@dataclass
class AnalyticsEvent:
    """Analytics event structure."""

    name: str
    category: EventCategory
    properties: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    organization_id: Optional[str] = None


@dataclass
class AnalyticsBatch:
    """Batch analytics request."""

    events: List[AnalyticsEvent]
    batch: bool = True
    context: Optional[Dict[str, Any]] = None


@dataclass
class AnalyticsResponse:
    """Response from analytics submission."""

    success: bool
    events_processed: int


@dataclass
class AnalyticsHealthResponse:
    """Analytics service health status."""

    status: str
    service: str
    timestamp: datetime
    supported_events: List[str]


# Training types
@dataclass
class TrainingExportRequest:
    """Request to export training data."""

    org_id: str
    format: TrainingFormat
    sft_format: Optional[SFTFormat] = None
    include_metadata: bool = True
    min_confidence: int = 1
    date_range: Optional[Dict[str, datetime]] = None
    max_records: Optional[int] = None
    normalize_scores: bool = True
    validate_output: bool = True


@dataclass
class FormatStats:
    """Statistics for a training format."""

    available: int
    last_exported: Optional[datetime] = None


@dataclass
class TrainingExportStats:
    """Statistics for training data exports."""

    stats: Dict[str, FormatStats]


@dataclass
class TrainingExportError:
    """Error response from training export."""

    error: str
    details: Dict[str, Any]


# Billing types
@dataclass
class BillingInfo:
    """Billing information."""

    success: bool
    billing: Dict[str, Any]


# Collaboration types
@dataclass
class Collaboration:
    """Collaboration session information."""

    id: str
    project_id: str
    status: Literal["active", "paused", "completed"]
    participants: List[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class ActiveCollaborationsResponse:
    """Response from active collaborations endpoint."""

    success: bool
    collaborations: List[Collaboration]


# Admin types
@dataclass
class AuditLog:
    """Audit log entry."""

    id: str
    timestamp: datetime
    action: str
    actor: str
    entity: str
    details: Dict[str, Any]


@dataclass
class AuditLogsResponse:
    """Response from audit logs endpoint."""

    success: bool
    logs: List[AuditLog]
    total: int


# Common response types
@dataclass
class ApiResponse:
    """Generic API response."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None


@dataclass
class ErrorResponse:
    """Error response structure."""

    error: str
    details: Optional[Dict[str, Any]] = None
    code: Optional[str] = None


@dataclass
class PaginatedResponse:
    """Paginated response structure."""

    data: List[Any]
    pagination: Dict[str, Any]


# Rate limiting types
@dataclass
class RateLimitInfo:
    """Rate limit information from response headers."""

    limit: int
    remaining: int
    reset: int
    retry_after: Optional[int] = None


# Webhook types
@dataclass
class WebhookConfig:
    """Webhook configuration."""

    url: str
    events: List[str]
    secret: Optional[str] = None
    active: bool = True


@dataclass
class WebhookEvent:
    """Webhook event payload."""

    id: str
    event: str
    data: Any
    timestamp: datetime
    delivery_id: str


# HTTP client types
@dataclass
class RetryConfig:
    """Retry configuration for HTTP requests."""

    max_retries: int
    backoff_factor: float
    status_forcelist: List[int]
    allowed_methods: List[str]


# Type aliases
Headers = Dict[str, str]
QueryParams = Dict[str, Union[str, int, bool, List[str]]]
JSONData = Dict[str, Any]


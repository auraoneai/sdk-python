"""Service modules for AuraOne API endpoints."""

# Import all service classes
from .auth import AuthService, AsyncAuthService
from .analytics import AnalyticsService, AsyncAnalyticsService
from .training import TrainingService, AsyncTrainingService
from .billing import BillingService, AsyncBillingService
from .collaboration import CollaborationService, AsyncCollaborationService
from .robotics import RoboticsService, AsyncRoboticsService
from .evaluations import EvaluationsService, AsyncEvaluationsService
from .labs import LabsService, AsyncLabsService
from .governance import GovernanceService, AsyncGovernanceService
from .integrations import IntegrationsService, AsyncIntegrationsService

__all__ = [
    "AuthService",
    "AsyncAuthService",
    "AnalyticsService",
    "AsyncAnalyticsService",
    "TrainingService",
    "AsyncTrainingService",
    "BillingService",
    "AsyncBillingService",
    "CollaborationService",
    "AsyncCollaborationService",
    "RoboticsService",
    "AsyncRoboticsService",
    "EvaluationsService",
    "AsyncEvaluationsService",
    "LabsService",
    "AsyncLabsService",
    "GovernanceService",
    "AsyncGovernanceService",
    "IntegrationsService",
    "AsyncIntegrationsService",
]

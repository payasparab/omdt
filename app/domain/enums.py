"""Domain enumerations for OMDT."""
from enum import Enum


class CanonicalState(str, Enum):
    """Canonical work-item lifecycle states (§12.5 / Appendix A)."""

    NEW = "new"
    TRIAGE = "triage"
    NEEDS_CLARIFICATION = "needs_clarification"
    READY_FOR_PRD = "ready_for_prd"
    PRD_DRAFTING = "prd_drafting"
    PRD_REVIEW = "prd_review"
    APPROVAL_PENDING = "approval_pending"
    APPROVED = "approved"
    READY_FOR_BUILD = "ready_for_build"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    VALIDATION = "validation"
    DEPLOYMENT_PENDING = "deployment_pending"
    DEPLOYED = "deployed"
    DONE = "done"
    ARCHIVED = "archived"


class WorkItemType(str, Enum):
    """Categorises the kind of work a work-item represents."""

    ANALYSIS_REQUEST = "analysis_request"
    DASHBOARD_REQUEST = "dashboard_request"
    PIPELINE_REQUEST = "pipeline_request"
    DATA_MODEL_REQUEST = "data_model_request"
    DATA_SCIENCE_REQUEST = "data_science_request"
    PAPER_REVIEW_REQUEST = "paper_review_request"
    DOCUMENTATION_REQUEST = "documentation_request"
    TRAINING_REQUEST = "training_request"
    ACCESS_REQUEST = "access_request"
    BUG_OR_INCIDENT = "bug_or_incident"
    VENDOR_OR_PROCUREMENT = "vendor_or_procurement"
    STATUS_OR_REPORTING = "status_or_reporting"
    UNKNOWN_NEEDS_CLARIFICATION = "unknown_needs_clarification"
    TASK = "task"
    BUG = "bug"
    DEPLOYMENT = "deployment"
    PIPELINE = "pipeline"
    INCIDENT = "incident"


class Priority(str, Enum):
    """Work-item priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ActorType(str, Enum):
    """Identifies who performed an action."""

    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class SourceChannel(str, Enum):
    """Channel through which a request or message arrived."""

    OUTLOOK = "outlook"
    LINEAR = "linear"
    NOTION = "notion"
    CLI = "cli"
    API = "api"
    EMAIL = "email"


class ArtifactType(str, Enum):
    """Types of artifacts stored in the artifact registry."""

    PRD = "prd"
    RESEARCH_BRIEF = "research_brief"
    LITERATURE_MATRIX = "literature_matrix"
    SQL_BUNDLE = "sql_bundle"
    NOTEBOOK = "notebook"
    DASHBOARD_SPEC = "dashboard_spec"
    DBML = "dbml"
    ARCHITECTURE_DIAGRAM = "architecture_diagram"
    DEPLOYMENT_MANIFEST = "deployment_manifest"
    EMAIL_PACKAGE = "email_package"
    PRESENTATION = "presentation"
    AUDIT_EXPORT = "audit_export"
    RUNBOOK = "runbook"
    RELEASE_NOTES = "release_notes"
    USER_GUIDE = "user_guide"
    TECHNICAL_MEMO = "technical_memo"
    SOP = "sop"
    TRAINING_PLAN = "training_plan"
    ONBOARDING_CHECKLIST = "onboarding_checklist"


class ApprovalStatus(str, Enum):
    """Status of an approval decision."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DeploymentState(str, Enum):
    """States in the deployment lifecycle (§17.6)."""

    BUILD_PENDING = "build_pending"
    BUILD_PASSED = "build_passed"
    DEPLOY_PENDING_APPROVAL = "deploy_pending_approval"
    DEPLOY_IN_PROGRESS = "deploy_in_progress"
    DEPLOY_SUCCEEDED = "deploy_succeeded"
    DEPLOY_FAILED = "deploy_failed"
    ROLLBACK_IN_PROGRESS = "rollback_in_progress"
    ROLLED_BACK = "rolled_back"


class AccessRequestState(str, Enum):
    """States in the access-request lifecycle (Appendix A.2)."""

    REQUESTED = "requested"
    POLICY_CHECK = "policy_check"
    APPROVAL_PENDING = "approval_pending"
    APPROVED = "approved"
    PROVISIONING = "provisioning"
    VERIFIED = "verified"
    CLOSED = "closed"


class PRDStatus(str, Enum):
    """Status of a PRD revision through its lifecycle."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


class RiskLevel(str, Enum):
    """Risk level assessment for work items."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PipelineType(str, Enum):
    """Types of managed pipelines (§17.2)."""

    SQL_TRANSFORMATION = "sql_transformation"
    PYTHON_BATCH = "python_batch"
    DATA_INGESTION = "data_ingestion"
    METRIC_REFRESH = "metric_refresh"
    MODEL_SCORING = "model_scoring"
    REPORT_GENERATION = "report_generation"
    SYNC_RECONCILIATION = "sync_reconciliation"
    MAINTENANCE_CLEANUP = "maintenance_cleanup"

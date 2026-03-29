"""Re-export Base and all table models for Alembic auto-detection."""
from app.db.tables import Base  # noqa: F401 — re-export
from app.db.tables import (  # noqa: F401
    ArtifactLinkRow,
    ArtifactRow,
    AuditEventRow,
    ConversationMessageRow,
    ConversationThreadRow,
    LinearLinkRow,
    PersonRow,
    PRDRevisionRow,
    ProjectRow,
    WorkItemRow,
)

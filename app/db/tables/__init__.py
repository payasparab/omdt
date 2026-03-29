"""SQLAlchemy table definitions — import all Row classes for Alembic discovery."""
from app.db.tables.artifacts import ArtifactLinkRow, ArtifactRow
from app.db.tables.audit_events import AuditEventRow
from app.db.tables.base import Base
from app.db.tables.conversation_messages import ConversationMessageRow
from app.db.tables.conversation_threads import ConversationThreadRow
from app.db.tables.identity import PersonRow
from app.db.tables.linear_links import LinearLinkRow
from app.db.tables.prd_revisions import PRDRevisionRow
from app.db.tables.projects import ProjectRow
from app.db.tables.work_items import WorkItemRow

__all__ = [
    "Base",
    "ArtifactLinkRow",
    "ArtifactRow",
    "AuditEventRow",
    "ConversationMessageRow",
    "ConversationThreadRow",
    "LinearLinkRow",
    "PersonRow",
    "PRDRevisionRow",
    "ProjectRow",
    "WorkItemRow",
]

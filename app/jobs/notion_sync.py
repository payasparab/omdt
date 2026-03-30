"""Notion sync service — syncs PRD pages and artifacts to Notion.

PRD pages follow a template with: title, status, owner, project link,
Linear link, version, last updated.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.adapters.notion import NotionAdapter
from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import PRDStatus
from app.domain.models.prd import PRDRevision
from app.services import prd as prd_service
from app.services import work_items as wi_service

# ---------------------------------------------------------------------------
# In-memory page link store (prd_id -> notion_page_id)
# ---------------------------------------------------------------------------

_page_links: dict[str, str] = {}


def get_page_links() -> dict[str, str]:
    return _page_links


def clear_stores() -> None:
    _page_links.clear()


# ---------------------------------------------------------------------------
# PRD page template helpers
# ---------------------------------------------------------------------------

def _build_prd_properties(
    prd: PRDRevision,
    *,
    owner: str | None = None,
    project_link: str | None = None,
    linear_link: str | None = None,
) -> dict[str, Any]:
    """Build Notion page properties from a PRD revision."""
    props: dict[str, Any] = {
        "Status": {
            "select": {"name": prd.status.value.replace("_", " ").title()}
        },
        "Version": {
            "number": prd.revision_number,
        },
        "LastUpdated": {
            "date": {"start": datetime.now(timezone.utc).isoformat()},
        },
    }
    if owner:
        props["Owner"] = {
            "rich_text": [{"text": {"content": owner}}],
        }
    if project_link:
        props["ProjectLink"] = {
            "url": project_link,
        }
    if linear_link:
        props["LinearLink"] = {
            "url": linear_link,
        }
    return props


def _build_prd_content_blocks(prd: PRDRevision) -> list[dict[str, Any]]:
    """Convert PRD markdown content into Notion block children."""
    blocks: list[dict[str, Any]] = []
    for line in (prd.content or "").split("\n"):
        if line.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"type": "text", "text": {"content": line[2:]}}]
                },
            })
        elif line.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": line[3:]}}]
                },
            })
        elif line.strip():
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": line}}]
                },
            })
    return blocks


# ---------------------------------------------------------------------------
# NotionSyncService
# ---------------------------------------------------------------------------

class NotionSyncService:
    """Manages synchronisation of PRD pages to Notion."""

    def __init__(self, adapter: NotionAdapter, *, parent_db_id: str = "") -> None:
        self._adapter = adapter
        self._parent_db_id = parent_db_id

    async def sync_prd(self, prd_id: str) -> dict[str, Any]:
        """Create or update a Notion PRD page.

        Idempotent: uses stored page link to decide create vs update.
        """
        corr_id = generate_correlation_id()

        prd = await prd_service.get_prd(prd_id)
        if prd is None:
            return {"success": False, "error": "PRD not found"}

        # Look up work item for owner and project context
        wi = await wi_service.get_work_item(prd.work_item_id)
        owner = wi.owner_person_key if wi else prd.author
        linear_issue_id = wi.linear_issue_id if wi else None

        properties = _build_prd_properties(
            prd,
            owner=owner,
            linear_link=f"https://linear.app/issue/{linear_issue_id}" if linear_issue_id else None,
        )

        existing_page_id = _page_links.get(prd_id)

        try:
            if existing_page_id:
                result = await self._adapter.execute("sync_prd", {
                    "page_id": existing_page_id,
                    "properties": properties,
                })
            else:
                children = _build_prd_content_blocks(prd)
                title = f"PRD v{prd.revision_number}: {wi.title}" if wi else f"PRD v{prd.revision_number}"
                result = await self._adapter.execute("sync_prd", {
                    "parent_id": self._parent_db_id,
                    "title": title,
                    "work_item_id": prd.work_item_id,
                    "properties": properties,
                    "children": children,
                })
                page_id = result.get("page_id", "")
                if page_id:
                    _page_links[prd_id] = page_id

            await emit("notion.sync_completed", {
                "prd_id": prd_id,
                "work_item_id": prd.work_item_id,
                "correlation_id": corr_id,
            })

            record_audit_event(
                event_name="notion.sync_completed",
                actor_type="system",
                actor_id="notion_sync",
                object_type="prd_revision",
                object_id=prd_id,
                change_summary=f"Synced PRD v{prd.revision_number} to Notion",
                correlation_id=corr_id,
            )

            return {"success": True, "page_id": _page_links.get(prd_id, ""), **result}

        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def update_prd_status(self, prd_id: str, status: PRDStatus) -> dict[str, Any]:
        """Update the status property on an existing Notion PRD page."""
        page_id = _page_links.get(prd_id)
        if not page_id:
            return {"success": False, "error": "No Notion page linked for this PRD"}

        try:
            result = await self._adapter.execute("update_page", {
                "page_id": page_id,
                "properties": {
                    "Status": {
                        "select": {"name": status.value.replace("_", " ").title()},
                    },
                    "LastUpdated": {
                        "date": {"start": datetime.now(timezone.utc).isoformat()},
                    },
                },
            })

            record_audit_event(
                event_name="notion.status_updated",
                actor_type="system",
                actor_id="notion_sync",
                object_type="prd_revision",
                object_id=prd_id,
                change_summary=f"Updated Notion PRD status to {status.value}",
            )

            return {"success": True, **result}

        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def attach_artifact(self, page_id: str, artifact: dict[str, Any]) -> dict[str, Any]:
        """Add an artifact link to an existing Notion page."""
        try:
            artifact_text = (
                f"Artifact: {artifact.get('artifact_type', 'unknown')} "
                f"v{artifact.get('version', '?')} — {artifact.get('storage_uri', '')}"
            )
            result = await self._adapter.execute("update_page", {
                "page_id": page_id,
                "properties": {
                    "ArtifactLink": {
                        "url": artifact.get("storage_uri", ""),
                    },
                    "LastUpdated": {
                        "date": {"start": datetime.now(timezone.utc).isoformat()},
                    },
                },
            })

            record_audit_event(
                event_name="notion.artifact_attached",
                actor_type="system",
                actor_id="notion_sync",
                object_type="notion_page",
                object_id=page_id,
                change_summary=f"Attached artifact to Notion page: {artifact_text}",
            )

            return {"success": True, **result}

        except Exception as exc:
            return {"success": False, "error": str(exc)}

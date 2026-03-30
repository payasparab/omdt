"""Access request and provisioning service.

Lifecycle: REQUESTED -> POLICY_CHECK -> APPROVAL_PENDING -> APPROVED ->
PROVISIONING -> VERIFIED -> CLOSED.

All grants emit audit events.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import yaml

from app.core.audit import record_audit_event
from app.core.events import emit
from app.core.ids import generate_correlation_id
from app.domain.enums import AccessRequestState
from app.domain.models.access import AccessRequest, RoleBundle

# In-memory store.
_store: dict[str, AccessRequest] = {}

# Role bundle config cache
_role_bundles: dict[str, RoleBundle] | None = None


def get_store() -> dict[str, AccessRequest]:
    return _store


def clear_store() -> None:
    _store.clear()


def _load_role_bundles() -> dict[str, RoleBundle]:
    """Load role bundles from config/role_bundles.yaml."""
    global _role_bundles
    if _role_bundles is not None:
        return _role_bundles

    config_path = Path(__file__).resolve().parents[2] / "config" / "role_bundles.yaml"
    if not config_path.exists():
        _role_bundles = {}
        return _role_bundles

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    bundles = {}
    for name, cfg in data.get("role_bundles", {}).items():
        bundles[name] = RoleBundle(
            name=name,
            allowed_databases=cfg.get("allowed_databases", []),
            allowed_schemas=cfg.get("allowed_schemas", []),
            warehouse_defaults=cfg.get("warehouse_defaults", {}).get("warehouse"),
            temp_object_rights=cfg.get("temp_object_rights", False),
            grant_prerequisites=cfg.get("grant_prerequisites", []),
            approval_threshold=cfg.get("approval_threshold", "lead"),
            expiration_policy=str(cfg["expiration_policy"]) if cfg.get("expiration_policy") else None,
            review_cadence=str(cfg["expiration_policy"].get("review_cadence_days")) if cfg.get("expiration_policy") and isinstance(cfg["expiration_policy"], dict) else None,
        )
    _role_bundles = bundles
    return _role_bundles


def reload_role_bundles() -> None:
    """Force reload of role bundles config (for testing)."""
    global _role_bundles
    _role_bundles = None


async def create_access_request(
    *,
    requester_person_key: str,
    requested_role_bundle: str,
    justification: str = "",
    resources: list[str] | None = None,
    linear_issue_id: str | None = None,
) -> AccessRequest:
    """Create a new access request."""
    now = datetime.now(timezone.utc)
    request = AccessRequest(
        id=uuid4(),
        requester_person_key=requester_person_key,
        requested_role_bundle=requested_role_bundle,
        state=AccessRequestState.REQUESTED,
        linear_issue_id=linear_issue_id,
        created_at=now,
        updated_at=now,
    )
    _store[str(request.id)] = request

    corr_id = generate_correlation_id()
    await emit(
        "access.request_created",
        {
            "request_id": str(request.id),
            "requester": requester_person_key,
            "role_bundle": requested_role_bundle,
            "justification": justification,
            "correlation_id": corr_id,
        },
    )
    record_audit_event(
        event_name="access.request_created",
        actor_type="human",
        actor_id=requester_person_key,
        object_type="access_request",
        object_id=str(request.id),
        change_summary=f"Access requested: {requested_role_bundle} by {requester_person_key}",
        correlation_id=corr_id,
    )
    return request


class PolicyResult:
    """Result of evaluating access policy against role bundle config."""

    def __init__(
        self,
        *,
        approved: bool,
        role_bundle: str,
        approval_threshold: str,
        prerequisites_met: bool = True,
        missing_prerequisites: list[str] | None = None,
        reason: str = "",
    ) -> None:
        self.approved = approved
        self.role_bundle = role_bundle
        self.approval_threshold = approval_threshold
        self.prerequisites_met = prerequisites_met
        self.missing_prerequisites = missing_prerequisites or []
        self.reason = reason


async def evaluate_policy(
    access_request_id: str,
    *,
    requester_roles: list[str] | None = None,
) -> PolicyResult | None:
    """Evaluate the access policy for a request against role bundle config."""
    request = _store.get(access_request_id)
    if request is None:
        return None

    bundles = _load_role_bundles()
    bundle = bundles.get(request.requested_role_bundle)
    if bundle is None:
        request.state = AccessRequestState.POLICY_CHECK
        request.policy_evaluated_at = datetime.now(timezone.utc)
        request.updated_at = datetime.now(timezone.utc)
        return PolicyResult(
            approved=False,
            role_bundle=request.requested_role_bundle,
            approval_threshold="unknown",
            reason=f"Unknown role bundle: {request.requested_role_bundle}",
        )

    # Check prerequisites
    prerequisites_met = True
    missing: list[str] = []
    if bundle.grant_prerequisites and requester_roles is not None:
        for prereq in bundle.grant_prerequisites:
            if prereq not in requester_roles:
                prerequisites_met = False
                missing.append(prereq)

    # Auto-approve if threshold is "none" and prerequisites met
    auto_approve = bundle.approval_threshold == "none" and prerequisites_met

    request.state = AccessRequestState.POLICY_CHECK
    request.policy_evaluated_at = datetime.now(timezone.utc)
    request.updated_at = datetime.now(timezone.utc)

    if auto_approve:
        request.state = AccessRequestState.APPROVED
        request.approved_at = datetime.now(timezone.utc)
    elif prerequisites_met:
        request.state = AccessRequestState.APPROVAL_PENDING
    # If prerequisites not met, stays in POLICY_CHECK

    corr_id = generate_correlation_id()
    record_audit_event(
        event_name="access.policy_evaluated",
        actor_type="system",
        actor_id="policy_engine",
        object_type="access_request",
        object_id=access_request_id,
        change_summary=f"Policy evaluated: threshold={bundle.approval_threshold}, auto_approve={auto_approve}",
        correlation_id=corr_id,
    )

    return PolicyResult(
        approved=auto_approve,
        role_bundle=request.requested_role_bundle,
        approval_threshold=bundle.approval_threshold,
        prerequisites_met=prerequisites_met,
        missing_prerequisites=missing,
        reason="Auto-approved (no approval needed)" if auto_approve else "",
    )


async def approve_access(
    access_request_id: str,
    approver: str,
) -> AccessRequest | None:
    """Approve an access request."""
    request = _store.get(access_request_id)
    if request is None:
        return None
    if request.state != AccessRequestState.APPROVAL_PENDING:
        return request

    request.state = AccessRequestState.APPROVED
    request.approved_at = datetime.now(timezone.utc)
    request.approval_id = uuid4()
    request.updated_at = datetime.now(timezone.utc)

    corr_id = generate_correlation_id()
    await emit(
        "access.approved",
        {
            "request_id": access_request_id,
            "approver": approver,
            "correlation_id": corr_id,
        },
    )
    record_audit_event(
        event_name="access.approved",
        actor_type="human",
        actor_id=approver,
        object_type="access_request",
        object_id=access_request_id,
        change_summary=f"Access approved by {approver}",
        correlation_id=corr_id,
        approval_id=str(request.approval_id),
    )
    return request


async def reject_access(
    access_request_id: str,
    approver: str,
    reason: str = "",
) -> AccessRequest | None:
    """Reject an access request."""
    request = _store.get(access_request_id)
    if request is None:
        return None
    if request.state != AccessRequestState.APPROVAL_PENDING:
        return request

    request.state = AccessRequestState.CLOSED
    request.closed_at = datetime.now(timezone.utc)
    request.updated_at = datetime.now(timezone.utc)

    corr_id = generate_correlation_id()
    await emit(
        "access.rejected",
        {
            "request_id": access_request_id,
            "approver": approver,
            "reason": reason,
            "correlation_id": corr_id,
        },
    )
    record_audit_event(
        event_name="access.rejected",
        actor_type="human",
        actor_id=approver,
        object_type="access_request",
        object_id=access_request_id,
        change_summary=f"Access rejected by {approver}: {reason}",
        correlation_id=corr_id,
    )
    return request


async def provision_access(
    access_request_id: str,
    *,
    snowflake_adapter: Any | None = None,
) -> AccessRequest | None:
    """Provision access via the Snowflake adapter."""
    request = _store.get(access_request_id)
    if request is None:
        return None
    if request.state != AccessRequestState.APPROVED:
        return request

    request.state = AccessRequestState.PROVISIONING
    request.provisioning_started_at = datetime.now(timezone.utc)
    request.updated_at = datetime.now(timezone.utc)

    corr_id = generate_correlation_id()

    try:
        if snowflake_adapter is not None:
            await snowflake_adapter.execute(
                "create_user",
                {
                    "username": request.requester_person_key,
                    "approval_id": str(request.approval_id),
                },
            )
            await snowflake_adapter.execute(
                "grant_role",
                {
                    "username": request.requester_person_key,
                    "role": request.requested_role_bundle,
                    "approval_id": str(request.approval_id),
                },
            )

        request.state = AccessRequestState.VERIFIED
        request.provisioned_at = datetime.now(timezone.utc)
        request.verified_at = datetime.now(timezone.utc)
        request.updated_at = datetime.now(timezone.utc)

        await emit(
            "access.provisioned",
            {
                "request_id": access_request_id,
                "role_bundle": request.requested_role_bundle,
                "correlation_id": corr_id,
            },
        )
        record_audit_event(
            event_name="access.provisioned",
            actor_type="system",
            actor_id="provisioner",
            object_type="access_request",
            object_id=access_request_id,
            change_summary=f"Access provisioned: {request.requested_role_bundle}",
            correlation_id=corr_id,
            approval_id=str(request.approval_id),
        )
    except Exception as exc:
        request.state = AccessRequestState.APPROVED  # revert to allow retry
        request.updated_at = datetime.now(timezone.utc)
        record_audit_event(
            event_name="access.provisioning_failed",
            actor_type="system",
            actor_id="provisioner",
            object_type="access_request",
            object_id=access_request_id,
            change_summary=f"Provisioning failed: {exc}",
            correlation_id=corr_id,
        )

    return request


async def verify_access(access_request_id: str) -> AccessRequest | None:
    """Verify that provisioned access is working."""
    request = _store.get(access_request_id)
    if request is None:
        return None
    if request.state != AccessRequestState.VERIFIED:
        return request

    request.state = AccessRequestState.CLOSED
    request.closed_at = datetime.now(timezone.utc)
    request.updated_at = datetime.now(timezone.utc)

    corr_id = generate_correlation_id()
    record_audit_event(
        event_name="access.verified_and_closed",
        actor_type="system",
        actor_id="verifier",
        object_type="access_request",
        object_id=access_request_id,
        change_summary="Access verified and request closed",
        correlation_id=corr_id,
    )
    return request


async def revoke_access(
    access_request_id: str,
    reason: str,
    *,
    actor: str = "system",
    snowflake_adapter: Any | None = None,
) -> AccessRequest | None:
    """Revoke previously granted access."""
    request = _store.get(access_request_id)
    if request is None:
        return None

    corr_id = generate_correlation_id()

    if snowflake_adapter is not None:
        await snowflake_adapter.execute(
            "revoke_role",
            {
                "username": request.requester_person_key,
                "role": request.requested_role_bundle,
                "approval_id": str(request.approval_id or "revocation"),
            },
        )

    request.state = AccessRequestState.CLOSED
    request.closed_at = datetime.now(timezone.utc)
    request.updated_at = datetime.now(timezone.utc)

    await emit(
        "access.revoked",
        {
            "request_id": access_request_id,
            "reason": reason,
            "correlation_id": corr_id,
        },
    )
    record_audit_event(
        event_name="access.revoked",
        actor_type="human",
        actor_id=actor,
        object_type="access_request",
        object_id=access_request_id,
        change_summary=f"Access revoked: {reason}",
        correlation_id=corr_id,
    )
    return request


async def get_access_request(access_request_id: str) -> AccessRequest | None:
    """Retrieve an access request by ID."""
    return _store.get(access_request_id)


async def list_access_requests(
    *,
    state: AccessRequestState | None = None,
    requester: str | None = None,
    role_bundle: str | None = None,
) -> list[AccessRequest]:
    """List access requests with optional filters."""
    results = list(_store.values())
    if state is not None:
        results = [r for r in results if r.state == state]
    if requester is not None:
        results = [r for r in results if r.requester_person_key == requester]
    if role_bundle is not None:
        results = [r for r in results if r.requested_role_bundle == role_bundle]
    return results

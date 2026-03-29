"""Security utilities — hashing, redaction, approval validation.

Implements helpers referenced by §23.2 (sensitive action classes) and
§15.7 (log redaction rules).
"""

from __future__ import annotations

import hashlib
from enum import StrEnum


# ---------------------------------------------------------------------------
# Sensitive action classes (§23.2)
# ---------------------------------------------------------------------------

class SensitiveActionClass(StrEnum):
    """Actions that require explicit approval or an allowlisted automation
    policy before execution."""

    PRODUCTION_DEPLOY = "production_deploy"
    PRODUCTION_ACCESS_GRANT = "production_access_grant"
    SECRETS_BACKEND_CHANGE = "secrets_backend_change"
    VENDOR_PROCUREMENT = "vendor_procurement"
    BROAD_EXTERNAL_COMMUNICATION = "broad_external_communication"
    DESTRUCTIVE_DATA_OPERATION = "destructive_data_operation"
    PROMPT_POLICY_CHANGE = "prompt_policy_change"


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_value(value: str) -> str:
    """Return the hex-encoded SHA-256 hash of *value*."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

def redact_secret(value: str) -> str:
    """Return only the last 4 characters of *value*, prefixed with ``****``.

    If the value is shorter than 5 characters the entire value is masked.
    """
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"


# ---------------------------------------------------------------------------
# Approval validation
# ---------------------------------------------------------------------------

def validate_approval_required(action_class: str, policy: dict[str, bool]) -> bool:
    """Return ``True`` if *action_class* requires approval according to
    *policy*.

    *policy* maps action class names to booleans.  If the action class is
    not present in the policy it is treated as requiring approval (fail-safe).
    """
    return policy.get(action_class, True)

"""Pydantic models for Snowflake role bundles (config/role_bundles.yaml) per PRD §16.6."""

from pydantic import BaseModel, ConfigDict


class WarehouseDefaults(BaseModel):
    """Default warehouse settings for a role bundle."""

    model_config = ConfigDict(strict=True)

    warehouse: str
    size: str


class ExpirationPolicy(BaseModel):
    """Expiration and review cadence for a role bundle."""

    model_config = ConfigDict(strict=True)

    days: int
    review_cadence_days: int


class RoleBundle(BaseModel):
    """A single Snowflake role bundle definition."""

    model_config = ConfigDict(strict=True)

    allowed_databases: list[str]
    warehouse_defaults: WarehouseDefaults
    approval_threshold: str
    expiration_policy: ExpirationPolicy


class RoleBundlesConfig(BaseModel):
    """Root config model matching config/role_bundles.yaml."""

    model_config = ConfigDict(strict=True)

    role_bundles: dict[str, RoleBundle]

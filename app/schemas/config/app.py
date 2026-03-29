"""Pydantic models for the main OMDT application config (config/omdt.yaml)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    model_config = ConfigDict(strict=True)

    url: str


class RedisConfig(BaseModel):
    """Redis connection configuration."""

    model_config = ConfigDict(strict=True)

    url: str


class SecretManagerConfig(BaseModel):
    """Secret manager backend configuration."""

    model_config = ConfigDict(strict=True)

    type: Literal["env", "vault", "aws_secrets_manager"]


class AdaptersConfig(BaseModel):
    """Enabled adapter configuration."""

    model_config = ConfigDict(strict=True)

    enabled: list[str]


class AppSection(BaseModel):
    """Core application metadata."""

    model_config = ConfigDict(strict=True)

    name: str
    version: str
    environment: Literal["development", "staging", "production"]
    debug: bool = False
    default_timezone: str = "UTC"


class OmdtAppConfig(BaseModel):
    """Root config model matching config/omdt.yaml."""

    model_config = ConfigDict(strict=True)

    app: AppSection
    database: DatabaseConfig
    redis: RedisConfig
    secret_manager: SecretManagerConfig
    adapters: AdaptersConfig

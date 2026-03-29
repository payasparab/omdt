"""Config loader for OMDT YAML configuration files.

Loads each YAML config, resolves environment variable references,
and validates against the corresponding Pydantic model.
"""

import os
import re
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from app.schemas.config.app import OmdtAppConfig
from app.schemas.config.approvals import ApprovalPolicyConfig
from app.schemas.config.linear import LinearSchemaConfig
from app.schemas.config.notifications import NotificationConfig
from app.schemas.config.people import PeopleConfig
from app.schemas.config.prompts import PromptRegistryConfig
from app.schemas.config.role_bundles import RoleBundlesConfig

T = TypeVar("T", bound=BaseModel)

_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)(?::-(.*?))?\}")

# Default config directory relative to the project root.
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def _resolve_env_vars(value: object) -> object:
    """Recursively resolve ${VAR:-default} patterns in config values."""
    if isinstance(value, str):
        def _replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            default = match.group(2)
            return os.environ.get(var_name, default if default is not None else match.group(0))

        return _ENV_VAR_PATTERN.sub(_replacer, value)
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def load_yaml(path: Path) -> dict:  # type: ignore[type-arg]
    """Load a YAML file and resolve environment variable references.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed and environment-resolved dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
    """
    with open(path) as f:
        raw = yaml.safe_load(f)
    if raw is None:
        return {}
    resolved: dict = _resolve_env_vars(raw)  # type: ignore[assignment]
    return resolved


def load_config(path: Path, model: type[T]) -> T:
    """Load a YAML config file and validate it against a Pydantic model.

    Args:
        path: Path to the YAML file.
        model: The Pydantic model class to validate against.

    Returns:
        A validated instance of the model.

    Raises:
        FileNotFoundError: If the config file does not exist.
        pydantic.ValidationError: If the config data fails validation.
    """
    data = load_yaml(path)
    return model.model_validate(data)


def get_config_path(filename: str) -> Path:
    """Return the full path for a config file in the default config directory.

    Args:
        filename: Name of the config file (e.g. 'omdt.yaml').

    Returns:
        Resolved Path to the config file.
    """
    return _CONFIG_DIR / filename


def get_settings() -> OmdtAppConfig:
    """Load and return the validated main application config.

    Returns:
        Validated OmdtAppConfig instance.
    """
    return load_config(get_config_path("omdt.yaml"), OmdtAppConfig)


def load_people_config() -> PeopleConfig:
    """Load and return the validated people config."""
    return load_config(get_config_path("people.yaml"), PeopleConfig)


def load_linear_config() -> LinearSchemaConfig:
    """Load and return the validated Linear schema config."""
    return load_config(get_config_path("linear.schema.yaml"), LinearSchemaConfig)


def load_notifications_config() -> NotificationConfig:
    """Load and return the validated notification config."""
    return load_config(get_config_path("notifications.yaml"), NotificationConfig)


def load_approvals_config() -> ApprovalPolicyConfig:
    """Load and return the validated approval policy config."""
    return load_config(get_config_path("approvals.yaml"), ApprovalPolicyConfig)


def load_role_bundles_config() -> RoleBundlesConfig:
    """Load and return the validated role bundles config."""
    return load_config(get_config_path("role_bundles.yaml"), RoleBundlesConfig)


def load_prompts_config() -> PromptRegistryConfig:
    """Load and return the validated prompt registry config."""
    return load_config(get_config_path("prompts.yaml"), PromptRegistryConfig)

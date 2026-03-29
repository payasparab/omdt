"""Adapter registry — discover, register, and manage adapter instances.

Loads enabled adapters from config/omdt.yaml and provides a central
lookup for the rest of the application.
"""

from __future__ import annotations

from typing import Any

from app.adapters.base import BaseAdapter, AdapterError
from app.core.logging import get_logger

logger = get_logger(component="adapter_registry")


class AdapterRegistry:
    """Central registry for adapter instances.

    Adapters are registered by name and can be retrieved individually
    or health-checked as a group.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, BaseAdapter] = {}

    def register(self, adapter: BaseAdapter) -> None:
        """Register an adapter instance by its ``name`` attribute."""
        if adapter.name in self._adapters:
            raise AdapterError(
                f"Adapter '{adapter.name}' is already registered",
                adapter_name=adapter.name,
            )
        self._adapters[adapter.name] = adapter
        logger.info("adapter.registered", adapter=adapter.name)

    def get(self, name: str) -> BaseAdapter:
        """Return the adapter registered under *name*.

        Raises ``AdapterError`` if not found.
        """
        adapter = self._adapters.get(name)
        if adapter is None:
            raise AdapterError(
                f"Adapter '{name}' is not registered",
                adapter_name=name,
            )
        return adapter

    def list_enabled(self) -> list[str]:
        """Return the names of all registered adapters."""
        return list(self._adapters.keys())

    async def healthcheck_all(self) -> dict[str, dict[str, Any]]:
        """Run healthcheck on every registered adapter and return results."""
        results: dict[str, dict[str, Any]] = {}
        for name, adapter in self._adapters.items():
            try:
                results[name] = await adapter.healthcheck()
            except Exception as exc:
                results[name] = {"healthy": False, "error": str(exc)}
        return results

    def __contains__(self, name: str) -> bool:
        return name in self._adapters

    def __len__(self) -> int:
        return len(self._adapters)


def build_registry_from_config(
    enabled: list[str],
    adapter_configs: dict[str, dict[str, Any]] | None = None,
    **kwargs: Any,
) -> AdapterRegistry:
    """Build an ``AdapterRegistry`` populated with the enabled adapters.

    *enabled* is the list of adapter names from ``config/omdt.yaml``.
    *adapter_configs* maps adapter name to its specific config dict.
    Extra *kwargs* are forwarded to each adapter constructor (e.g.
    ``audit_writer``, ``event_bus``).
    """
    from app.adapters.snowflake import SnowflakeAdapter
    from app.adapters.linear import LinearAdapter
    from app.adapters.notion import NotionAdapter
    from app.adapters.outlook import OutlookAdapter
    from app.adapters.gamma import GammaAdapter
    from app.adapters.lovable import LovableAdapter
    from app.adapters.github import GitHubAdapter
    from app.adapters.render import RenderAdapter

    _ADAPTER_CLASSES: dict[str, type[BaseAdapter]] = {
        "snowflake": SnowflakeAdapter,
        "linear": LinearAdapter,
        "notion": NotionAdapter,
        "outlook": OutlookAdapter,
        "gamma": GammaAdapter,
        "lovable": LovableAdapter,
        "github": GitHubAdapter,
        "render": RenderAdapter,
    }

    configs = adapter_configs or {}
    registry = AdapterRegistry()

    for name in enabled:
        cls = _ADAPTER_CLASSES.get(name)
        if cls is None:
            logger.warning("adapter.unknown", adapter=name)
            continue
        adapter = cls(config=configs.get(name, {}), **kwargs)
        registry.register(adapter)

    return registry

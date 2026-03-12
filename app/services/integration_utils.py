from __future__ import annotations

from typing import Any

from app.db.models import Project, ProjectIntegration


def get_enabled_integration(project: Project, integration_type: str) -> ProjectIntegration | None:
    for integration in project.integrations:
        if integration.integration_type == integration_type and integration.is_enabled:
            return integration
    return None


def get_integration_config(integration: ProjectIntegration) -> dict[str, Any]:
    config = integration.config_json or {}
    if isinstance(config, dict):
        return config
    return {"value": config}


def get_config_value(config: dict[str, Any], key: str, default: Any = None) -> Any:
    if key in config:
        return config[key]
    return default

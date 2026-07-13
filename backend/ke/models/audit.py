from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from shared.models.base import BaseSchema, TenantScopedModel


class AuditAction:
    QUERY_EXECUTED = "query.executed"
    QUERY_BLOCKED = "query.blocked"
    SCHEMA_SYNCED = "schema.synced"
    GRAPH_UPDATED = "graph.updated"
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    API_KEY_CREATED = "auth.api_key.created"
    API_KEY_REVOKED = "auth.api_key.revoked"


class AuditEntry(TenantScopedModel):
    id: str
    actor_id: str | None = None
    action: str
    resource_type: str = ""
    resource_id: str = ""
    details: dict[str, Any] = {}
    ip_address: str = ""
    user_agent: str = ""
    outcome: str = "success"
    created_at: datetime = datetime.now(UTC)

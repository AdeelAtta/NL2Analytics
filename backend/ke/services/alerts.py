from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class AlertSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertCategory(StrEnum):
    SYNC_FAILURE = "sync_failure"
    QUALITY_DROP = "quality_drop"
    SCHEMA_CHANGE = "schema_change"
    PII_DETECTED = "pii_detected"
    STALE_DATA = "stale_data"


@dataclass
class Alert:
    tenant_id: str
    category: AlertCategory
    severity: AlertSeverity
    title: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
        }


AlertHandler = Callable[[Alert], None]


class AlertService:
    def __init__(self) -> None:
        self._handlers: list[AlertHandler] = []
        self._alerts: list[Alert] = []

    def register_handler(self, handler: AlertHandler) -> None:
        self._handlers.append(handler)

    def emit(self, alert: Alert) -> None:
        self._alerts.append(alert)
        logger.info("Alert emitted: [%s] %s — %s", alert.severity.value, alert.category.value, alert.title)
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.exception("Alert handler failed: %s", e)

    def get_alerts(
        self,
        tenant_id: str | None = None,
        category: AlertCategory | None = None,
        severity: AlertSeverity | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        filtered = list(self._alerts)
        if tenant_id:
            filtered = [a for a in filtered if a.tenant_id == tenant_id]
        if category:
            filtered = [a for a in filtered if a.category == category]
        if severity:
            filtered = [a for a in filtered if a.severity == severity]
        return [a.to_dict() for a in filtered[-limit:]]

    def sync_failure_alert(
        self,
        tenant_id: str,
        database_id: str,
        database_name: str,
        error_message: str,
    ) -> Alert:
        alert = Alert(
            tenant_id=tenant_id,
            category=AlertCategory.SYNC_FAILURE,
            severity=AlertSeverity.HIGH,
            title=f"Sync failed: {database_name}",
            message=f"Database sync failed for {database_name}: {error_message}",
            details={
                "database_id": database_id,
                "database_name": database_name,
                "error": error_message,
            },
        )
        self.emit(alert)
        return alert

    def quality_drop_alert(
        self,
        tenant_id: str,
        previous_score: float,
        current_score: float,
        threshold: float = 0.1,
    ) -> Alert | None:
        drop = previous_score - current_score
        if drop >= threshold:
            severity = AlertSeverity.HIGH if drop >= 0.3 else AlertSeverity.MEDIUM
            alert = Alert(
                tenant_id=tenant_id,
                category=AlertCategory.QUALITY_DROP,
                severity=severity,
                title=f"Quality score dropped by {drop:.1%}",
                message=f"Schema quality dropped from {previous_score:.2f} to {current_score:.2f}",
                details={
                    "previous_score": previous_score,
                    "current_score": current_score,
                    "drop": round(drop, 4),
                    "threshold": threshold,
                },
            )
            self.emit(alert)
            return alert
        return None

    def schema_change_alert(
        self,
        tenant_id: str,
        database_name: str,
        change_type: str,
        object_name: str,
        details: dict[str, Any] | None = None,
    ) -> Alert:
        alert = Alert(
            tenant_id=tenant_id,
            category=AlertCategory.SCHEMA_CHANGE,
            severity=AlertSeverity.MEDIUM if change_type in ("TABLE_DROPPED", "COLUMN_DROPPED") else AlertSeverity.LOW,
            title=f"Schema change: {change_type} — {object_name}",
            message=f"{change_type} detected for {object_name} in {database_name}",
            details={
                "database_name": database_name,
                "change_type": change_type,
                "object_name": object_name,
                **(details or {}),
            },
        )
        self.emit(alert)
        return alert

    def pii_detected_alert(
        self,
        tenant_id: str,
        column_name: str,
        table_name: str,
        category: str,
        sensitivity: str,
    ) -> Alert:
        alert = Alert(
            tenant_id=tenant_id,
            category=AlertCategory.PII_DETECTED,
            severity=AlertSeverity.HIGH if sensitivity == "high" else AlertSeverity.MEDIUM,
            title=f"PII detected: {table_name}.{column_name}",
            message=f"Column {column_name} in {table_name} classified as {category} ({sensitivity} sensitivity)",
            details={
                "column_name": column_name,
                "table_name": table_name,
                "pii_category": category,
                "sensitivity": sensitivity,
            },
        )
        self.emit(alert)
        return alert

    def stale_data_alert(
        self,
        tenant_id: str,
        database_name: str,
        days_since_sync: int,
    ) -> Alert:
        alert = Alert(
            tenant_id=tenant_id,
            category=AlertCategory.STALE_DATA,
            severity=AlertSeverity.LOW if days_since_sync < 30 else AlertSeverity.MEDIUM,
            title=f"Stale data: {database_name} not synced for {days_since_sync}d",
            message=f"Database {database_name} has not been synced for {days_since_sync} days",
            details={
                "database_name": database_name,
                "days_since_sync": days_since_sync,
            },
        )
        self.emit(alert)
        return alert

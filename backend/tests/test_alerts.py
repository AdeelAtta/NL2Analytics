from __future__ import annotations

from unittest.mock import MagicMock

from ke.services.alerts import Alert, AlertCategory, AlertService, AlertSeverity


class TestAlertService:
    def setup_method(self):
        self.service = AlertService()

    def test_sync_failure_alert(self):
        alert = self.service.sync_failure_alert("tenant1", "db1", "testdb", "connection refused")
        assert alert.tenant_id == "tenant1"
        assert alert.category == AlertCategory.SYNC_FAILURE
        assert alert.severity == AlertSeverity.HIGH
        assert "connection refused" in alert.message

    def test_quality_drop_alert_below_threshold(self):
        alert = self.service.quality_drop_alert("tenant1", 0.9, 0.85, threshold=0.1)
        assert alert is None

    def test_quality_drop_alert_above_threshold(self):
        alert = self.service.quality_drop_alert("tenant1", 0.9, 0.7, threshold=0.1)
        assert alert is not None
        assert alert.category == AlertCategory.QUALITY_DROP
        assert alert.severity == AlertSeverity.MEDIUM

    def test_quality_drop_alert_critical(self):
        alert = self.service.quality_drop_alert("tenant1", 0.9, 0.5, threshold=0.1)
        assert alert is not None
        assert alert.severity == AlertSeverity.HIGH

    def test_quality_drop_alert_medium(self):
        alert = self.service.quality_drop_alert("tenant1", 0.8, 0.65, threshold=0.1)
        assert alert is not None
        assert alert.severity == AlertSeverity.MEDIUM

    def test_schema_change_alert_drop(self):
        alert = self.service.schema_change_alert("tenant1", "testdb", "COLUMN_DROPPED", "users.email")
        assert alert.category == AlertCategory.SCHEMA_CHANGE
        assert alert.severity == AlertSeverity.MEDIUM

    def test_schema_change_alert_add(self):
        alert = self.service.schema_change_alert("tenant1", "testdb", "TABLE_ADDED", "orders")
        assert alert.category == AlertCategory.SCHEMA_CHANGE
        assert alert.severity == AlertSeverity.LOW

    def test_pii_detected_alert_high(self):
        alert = self.service.pii_detected_alert("tenant1", "ssn", "employees", "ssn", "high")
        assert alert.category == AlertCategory.PII_DETECTED
        assert alert.severity == AlertSeverity.HIGH

    def test_pii_detected_alert_medium(self):
        alert = self.service.pii_detected_alert("tenant1", "city", "users", "address", "low")
        assert alert.severity == AlertSeverity.MEDIUM

    def test_stale_data_alert_fresh(self):
        alert = self.service.stale_data_alert("tenant1", "testdb", 7)
        assert alert.category == AlertCategory.STALE_DATA
        assert alert.severity == AlertSeverity.LOW

    def test_stale_data_alert_stale(self):
        alert = self.service.stale_data_alert("tenant1", "testdb", 45)
        assert alert.severity == AlertSeverity.MEDIUM

    def test_emit_and_retrieve(self):
        self.service.sync_failure_alert("tenant1", "db1", "testdb", "error")
        self.service.quality_drop_alert("tenant1", 0.9, 0.5, threshold=0.1)
        self.service.pii_detected_alert("tenant1", "email", "users", "email", "high")

        all_alerts = self.service.get_alerts()
        assert len(all_alerts) == 3

        sync_alerts = self.service.get_alerts(category=AlertCategory.SYNC_FAILURE)
        assert len(sync_alerts) == 1

        high_alerts = self.service.get_alerts(severity=AlertSeverity.HIGH)
        assert len(high_alerts) >= 2

    def test_filter_by_tenant(self):
        self.service.sync_failure_alert("tenant1", "db1", "db1", "err")
        self.service.sync_failure_alert("tenant2", "db2", "db2", "err")
        tenant1_alerts = self.service.get_alerts(tenant_id="tenant1")
        assert len(tenant1_alerts) == 1

    def test_handler_called(self):
        handler = MagicMock()
        self.service.register_handler(handler)
        self.service.sync_failure_alert("tenant1", "db1", "testdb", "error")
        handler.assert_called_once()
        args = handler.call_args
        assert args is not None
        assert isinstance(args[0][0], Alert)

    def test_handler_failure_does_not_crash(self):
        def failing_handler(alert):
            raise ValueError("handler failed")

        self.service.register_handler(failing_handler)
        self.service.sync_failure_alert("tenant1", "db1", "testdb", "error")
        assert len(self.service.get_alerts()) == 1

    def test_alert_to_dict(self):
        alert = Alert(
            tenant_id="t1",
            category=AlertCategory.SYNC_FAILURE,
            severity=AlertSeverity.HIGH,
            title="Test alert",
            message="Test message",
            details={"key": "value"},
        )
        d = alert.to_dict()
        assert d["tenant_id"] == "t1"
        assert d["category"] == "sync_failure"
        assert d["severity"] == "high"
        assert d["title"] == "Test alert"
        assert d["details"]["key"] == "value"
        assert d["acknowledged"] is False

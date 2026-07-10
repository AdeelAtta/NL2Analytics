from __future__ import annotations

from datetime import UTC, datetime

from ke.models.schema import Column
from ke.services.pii import PIIDetector

_NOW = datetime.now(UTC)


def _make_col(name: str, data_type: str = "text") -> Column:
    return Column(
        id=f"c_{name}",
        table_id="t1",
        name=name,
        ordinal_position=1,
        data_type=data_type,
        is_nullable=True,
        is_primary_key=False,
        is_unique=False,
        created_at=_NOW,
        updated_at=_NOW,
    )


class TestPIIDetector:
    def setup_method(self):
        self.detector = PIIDetector()

    def test_detect_email(self):
        col = _make_col("email")
        result = self.detector.classify_column(col)
        assert result is not None
        assert result["category"] == "email"
        assert result["sensitivity"] == "high"

    def test_detect_ssn(self):
        col = _make_col("ssn")
        result = self.detector.classify_column(col)
        assert result is not None
        assert result["category"] == "ssn"
        assert result["sensitivity"] == "high"

    def test_detect_phone(self):
        for name in ["phone", "phone_number", "mobile", "cell"]:
            col = _make_col(name)
            result = self.detector.classify_column(col)
            assert result is not None, f"Failed to detect {name}"
            assert result["category"] == "phone"

    def test_detect_password(self):
        col = _make_col("password_hash")
        result = self.detector.classify_column(col)
        assert result is not None
        assert result["category"] == "password"

    def test_detect_credit_card(self):
        for name in ["credit_card", "cc_number", "cvv"]:
            col = _make_col(name)
            result = self.detector.classify_column(col)
            assert result is not None, f"Failed to detect {name}"
            assert result["category"] == "credit_card"

    def test_detect_date_of_birth(self):
        for name in ["dob", "date_of_birth", "birth_date"]:
            col = _make_col(name)
            result = self.detector.classify_column(col)
            assert result is not None, f"Failed to detect {name}"
            assert result["category"] == "date_of_birth"

    def test_detect_address(self):
        col = _make_col("address")
        result = self.detector.classify_column(col)
        assert result is not None
        assert result["category"] == "address"

    def test_detect_name(self):
        col = _make_col("first_name")
        result = self.detector.classify_column(col)
        assert result is not None
        assert result["category"] == "name"

    def test_non_pii_column(self):
        col = _make_col("created_at")
        result = self.detector.classify_column(col)
        assert result is None

    def test_classify_columns_multiple(self):
        cols = [
            _make_col("email"),
            _make_col("created_at"),
            _make_col("ssn"),
            _make_col("total_amount", "numeric"),
        ]
        results = self.detector.classify_columns(cols)
        assert len(results) == 2
        categories = {r["category"] for r in results}
        assert categories == {"email", "ssn"}

    def test_summarize(self):
        cols = [
            _make_col("email"),
            _make_col("phone"),
            _make_col("ssn"),
            _make_col("created_at"),
            _make_col("first_name"),
        ]
        summary = self.detector.summarize(cols)
        assert summary["total_columns"] == 5
        assert summary["pii_columns"] == 4
        assert summary["by_category"]["email"] == 1
        assert summary["by_category"]["phone"] == 1
        assert summary["by_category"]["ssn"] == 1
        assert summary["by_category"]["name"] == 1
        assert summary["by_sensitivity"]["high"] == 3
        assert summary["by_sensitivity"]["low"] == 1

    def test_summarize_no_pii(self):
        cols = [_make_col("id"), _make_col("created_at")]
        summary = self.detector.summarize(cols)
        assert summary["pii_columns"] == 0
        assert summary["pii_pct"] == 0.0

    def test_detect_api_key(self):
        col = _make_col("api_key")
        result = self.detector.classify_column(col)
        assert result is not None
        assert result["category"] == "api_key"

    def test_detect_token(self):
        col = _make_col("auth_token")
        result = self.detector.classify_column(col)
        assert result is not None
        assert result["category"] == "token"

    def test_detect_bank_account(self):
        col = _make_col("bank_account_number")
        result = self.detector.classify_column(col)
        assert result is not None
        assert result["category"] == "bank_account"

    def test_detect_ip_address(self):
        col = _make_col("ip_address")
        result = self.detector.classify_column(col)
        assert result is not None
        assert result["category"] == "ip_address"

    def test_detect_health(self):
        col = _make_col("medical_record")
        result = self.detector.classify_column(col)
        assert result is not None
        assert result["category"] == "health"

    def test_detect_financial(self):
        col = _make_col("salary")
        result = self.detector.classify_column(col)
        assert result is not None
        assert result["category"] == "financial"

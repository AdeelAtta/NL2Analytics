from __future__ import annotations

import re
from typing import Any, Literal

from ke.models.schema import Column as ColumnModel

PIICategory = Literal[
    "email",
    "phone",
    "ssn",
    "credit_card",
    "password",
    "address",
    "name",
    "date_of_birth",
    "ip_address",
    "bank_account",
    "api_key",
    "token",
    "health",
    "financial",
    "location",
    "other",
]


class PIIPattern:
    def __init__(
        self,
        category: PIICategory,
        patterns: list[str],
        sensitivity: Literal["high", "medium", "low"] = "medium",
    ) -> None:
        self.category = category
        self.compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        self.sensitivity = sensitivity

    def match(self, name: str) -> bool:
        normalized = name.replace("_", " ").replace("-", " ").lower()
        return any(p.search(normalized) is not None for p in self.compiled)


_PII_RULES: list[PIIPattern] = [
    PIIPattern("email", [r"\bemail\b", r"\be\s*mail\b"], "high"),
    PIIPattern("phone", [r"\bphone\b", r"\btelephone\b", r"\bmobile\b", r"\bcell\b", r"\bfax\b"], "high"),
    PIIPattern("ssn", [r"\bssn\b", r"\bsocial\s+security\b", r"\bsin\b", r"\bnational\s+id\b"], "high"),
    PIIPattern("credit_card", [r"\bcredit\s+card\b", r"\bcc\s+number\b", r"\bccn\b", r"\bcvv\b", r"\bcvc\b", r"\bpan\b", r"\bcard\s+number\b"], "high"),
    PIIPattern("password", [r"\bpassword\b", r"\bpwd\b", r"\bpasswd\b", r"\bsecret\b"], "high"),
    PIIPattern("api_key", [r"\bapi\s+key\b", r"\bapikey\b", r"\bapi\s+secret\b"], "high"),
    PIIPattern("token", [r"\btoken\b", r"\brefresh\s+token\b", r"\baccess\s+token\b", r"\bauth\s+token\b"], "high"),
    PIIPattern("ip_address", [r"\bip\s+address\b", r"\bipaddr\b"], "medium"),
    PIIPattern("date_of_birth", [r"\bdob\b", r"\bdate\s+of\s+birth\b", r"\bbirth\s+date\b", r"\bbirthday\b", r"\bbirth\s+year\b"], "medium"),
    PIIPattern("address", [r"\baddress\b", r"\bstreet\b", r"\bzip\b", r"\bzipcode\b", r"\bpostal\b", r"\bcity\b", r"\bstate\b", r"\bcountry\b", r"\bprovince\b"], "low"),
    PIIPattern("name", [r"\bfirst\s+name\b", r"\blast\s+name\b", r"\bmiddle\s+name\b", r"\bfull\s+name\b", r"\busername\b"], "low"),
    PIIPattern("bank_account", [r"\bbank\s+account\b", r"\baccount\s+number\b", r"\brouting\b", r"\biban\b", r"\bswift\b", r"\bbic\b"], "high"),
    PIIPattern("health", [r"\bdiagnos[ei]s\b", r"\bmedical\b", r"\bpatient\b", r"\bhealth\s+record\b", r"\binsurance\s+id\b", r"\bhipaa\b"], "high"),
    PIIPattern("financial", [r"\bsalary\b", r"\bincome\b", r"\bwage\b", r"\bcompensation\b", r"\bpayroll\b"], "medium"),
    PIIPattern("location", [r"\blatitude\b", r"\blongitude\b", r"\bgeo\b", r"\bgps\b", r"\bcoordinates\b"], "low"),
]


class PIIDetector:
    def classify_column(self, column: ColumnModel) -> dict[str, Any] | None:
        for rule in _PII_RULES:
            if rule.match(column.name):
                return {
                    "column_id": column.id,
                    "column_name": column.name,
                    "table_id": column.table_id,
                    "category": rule.category,
                    "sensitivity": rule.sensitivity,
                    "data_type": column.data_type,
                }
        return None

    def classify_columns(self, columns: list[ColumnModel]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for col in columns:
            result = self.classify_column(col)
            if result is not None:
                results.append(result)
        return results

    def summarize(self, columns: list[ColumnModel]) -> dict[str, Any]:
        classified = self.classify_columns(columns)
        by_category: dict[str, int] = {}
        by_sensitivity: dict[str, int] = {}
        for item in classified:
            cat = item["category"]
            by_category[cat] = by_category.get(cat, 0) + 1
            sens = item["sensitivity"]
            by_sensitivity[sens] = by_sensitivity.get(sens, 0) + 1
        return {
            "total_columns": len(columns),
            "pii_columns": len(classified),
            "pii_pct": round(len(classified) / len(columns) * 100, 1) if columns else 0.0,
            "by_category": by_category,
            "by_sensitivity": by_sensitivity,
            "columns": classified,
        }

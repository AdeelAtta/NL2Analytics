from __future__ import annotations

import json
import os
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
_PATH = os.path.join(DATA_DIR, "schemas.json")


def _load() -> dict[str, Any]:
    if not os.path.exists(_PATH):
        return {}
    try:
        with open(_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_PATH, "w") as f:
        json.dump(data, f, indent=2)


def store_schema(tenant_id: str, tables: list[dict[str, Any]], columns: list[dict[str, Any]],
                 relationships: list[dict[str, Any]] | None = None) -> None:
    data = _load()
    entry = data.get(tenant_id, {})
    entry["tables"] = tables
    entry["columns"] = columns
    if relationships:
        entry["relationships"] = relationships
    data[tenant_id] = entry
    _save(data)


def get_sample_rows(tenant_id: str, table_name: str) -> list[dict[str, Any]]:
    data = _load()
    entry = data.get(tenant_id)
    if not entry:
        return []
    for t in entry.get("tables", []):
        if t.get("name", "").lower() == table_name.lower():
            return t.get("sample_rows", [])
    return []


def store_connection(tenant_id: str, conn_info: dict[str, Any]) -> None:
    data = _load()
    entry = data.get(tenant_id, {})
    entry["connection"] = conn_info
    data[tenant_id] = entry
    _save(data)


def get_connection(tenant_id: str) -> dict[str, Any] | None:
    data = _load()
    entry = data.get(tenant_id)
    if entry and "connection" in entry:
        return entry["connection"]
    return None


def get_schema(tenant_id: str) -> dict[str, Any] | None:
    data = _load()
    return data.get(tenant_id)


def has_schema(tenant_id: str) -> bool:
    data = _load()
    return tenant_id in data


def clear_schema(tenant_id: str) -> None:
    data = _load()
    data.pop(tenant_id, None)
    _save(data)


def list_tenants() -> list[str]:
    data = _load()
    return list(data.keys())


def build_ddl(tables: list[dict[str, Any]], columns: list[dict[str, Any]],
              relationships: list[dict[str, Any]] | None = None) -> str:
    lines: list[str] = []
    for tbl in tables:
        tbl_name = tbl["name"]
        tbl_desc = tbl.get("description", "")
        tbl_cols = [c for c in columns if c.get("table_name", "").lower() == tbl_name.lower()]
        desc = f" -- {tbl_desc}" if tbl_desc else ""
        lines.append(f"CREATE TABLE {tbl_name}{desc} (")
        for col in tbl_cols:
            parts = [f"  {col['name']} {col['data_type']}"]
            if col.get("is_primary_key"):
                parts.append("PRIMARY KEY")
            if not col.get("is_nullable", True):
                parts.append("NOT NULL")
            col_desc = col.get("description", "")
            if col_desc:
                parts[-1] += f" -- {col_desc}"
            lines.append(" ".join(parts))
        lines.append(");")
        if relationships:
            for rel in relationships:
                if rel.get("source_table", "").lower() == tbl_name.lower():
                    lines.append(f"-- {rel['source_table']}.{rel['source_column']} -> "
                                 f"{rel['target_table']}.{rel['target_column']}")
    return "\n".join(lines)

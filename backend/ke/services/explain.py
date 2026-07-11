from __future__ import annotations

import re
from typing import Any


def explain_sql(sql: str, query: str = "") -> str:
    if not sql or not sql.strip():
        return "No SQL was generated for this query."

    parts: list[str] = []
    sql_lower = sql.lower().strip().rstrip(";")

    tables = _extract_tables(sql_lower)
    columns = _extract_columns(sql_lower, sql)
    has_agg, agg_funcs = _extract_aggregations(sql_lower)
    filters = _extract_filters(sql_lower)
    joins = _extract_joins(sql_lower)
    order = _extract_order(sql_lower)
    limit = _extract_limit(sql_lower)

    if not tables:
        return f"The query generates SQL based on your request. The generated SQL is: {sql}"

    action = "gets" if not has_agg else "calculates"
    table_list = ", ".join(tables)

    parts.append(f"This query {action} data from the **{table_list}** table")

    if joins:
        join_desc = []
        for j in joins:
            join_desc.append(f"joined with **{j}**")
        parts[-1] += " " + ", ".join(join_desc)

    if has_agg and agg_funcs:
        agg_desc = []
        for func, col in agg_funcs:
            fn = func.lower()
            if col and col != "*":
                if fn == "sum":
                    agg_desc.append(f"the total of **{col}**")
                elif fn == "count":
                    agg_desc.append(f"the count of **{col}**")
                elif fn == "avg":
                    agg_desc.append(f"the average of **{col}**")
                else:
                    agg_desc.append(f"the {fn} of **{col}**")
            else:
                agg_desc.append(f"the {fn}")
        if agg_desc:
            parts.append("Calculating " + ", ".join(agg_desc))

    if columns and columns != ["*"]:
        cols_str = ", ".join(f"**{c}**" for c in columns)
        parts.append(f"Retrieving the following columns: {cols_str}")

    if filters:
        filter_parts = []
        for col, op, val in filters:
            if op == "=":
                filter_parts.append(f"**{col}** is **{val}**")
            elif op.lower() == "between":
                filter_parts.append(f"**{col}** is between **{val}**")
            else:
                filter_parts.append(f"**{col}** {op} **{val}**")
        parts.append(f"Filtering to only include rows where " + " and ".join(filter_parts))

    if order:
        order_col, direction = order
        dir_word = "ascending" if direction == "asc" else "descending"
        parts.append(f"Results are sorted by **{order_col}** in {dir_word} order")

    if limit:
        parts.append(f"Only the first **{limit}** results are shown")

    result = ". ".join(parts) + "."
    return result


def _extract_tables(sql: str) -> list[str]:
    tables: list[str] = []
    for m in re.finditer(r"\b(?:from|join|update|into)\s+(\w+)", sql, re.I):
        t = m.group(1).lower()
        if t not in tables and t not in ("select", "where", "set", "values", "on"):
            tables.append(t)
    return tables


def _extract_columns(sql: str, original: str) -> list[str]:
    m = re.match(r"select\s+(.*?)\s+from", sql, re.I | re.DOTALL)
    if not m:
        return []
    cols_str = m.group(1).strip()
    if cols_str == "*":
        return ["*"]
    cols = [c.strip().split(" as ")[-1].strip().strip('"') for c in cols_str.split(",")]
    return [c for c in cols if c and c not in ("distinct",) and not re.match(r"^[a-z]+\(", c)]


def _extract_aggregations(sql: str) -> tuple[bool, list[tuple[str, str]]]:
    funcs = re.findall(r"(avg|count|sum|min|max|date_trunc)\s*\(\s*(.*?)\s*\)", sql, re.I)
    return (bool(funcs), [(f[0].upper(), f[1].strip()) for f in funcs])


def _extract_filters(sql: str) -> list[tuple[str, str, str]]:
    filters: list[tuple[str, str, str]] = []
    where_match = re.search(r"where\s+(.+?)(?:\s+order\s+by|\s+limit|\s+group\s+by|$)", sql, re.I | re.DOTALL)
    if not where_match:
        return filters
    where_clause = where_match.group(1).strip()
    conditions = re.findall(r"(\w+)\s*(=|!=|<>|<|>|<=|>=|like|ilike|between|is)\s*'([^']+)'", where_clause, re.I)
    for col, op, val in conditions:
        filters.append((col.lower(), op.upper(), val))
    return filters


def _extract_joins(sql: str) -> list[str]:
    joins: list[str] = []
    for m in re.finditer(r"(?:join|inner\s+join|left\s+join|right\s+join)\s+(\w+)", sql, re.I):
        joins.append(m.group(1).lower())
    return joins


def _extract_order(sql: str) -> tuple[str, str] | None:
    m = re.search(r"order\s+by\s+(\w+)\s*(asc|desc)?", sql, re.I)
    if m:
        return (m.group(1).lower(), (m.group(2) or "asc").lower())
    return None


def _extract_limit(sql: str) -> int | None:
    m = re.search(r"limit\s+(\d+)", sql, re.I)
    return int(m.group(1)) if m else None


def extract_columns(sql: str) -> list[dict[str, str]]:
    from ke.services.demo_data import DEMO_COLUMNS, DEMO_TABLES

    if not sql or not sql.strip():
        return []
    sql_lower = sql.lower().strip().rstrip(";")
    tables_in_sql = set(_extract_tables(sql_lower))
    matched_cols = []
    for col in DEMO_COLUMNS:
        t = col.get("table_name", "").lower() if isinstance(col, dict) else ""
        if t in tables_in_sql:
            matched_cols.append({
                "name": col.get("name", "") if isinstance(col, dict) else "",
                "type": col.get("data_type", "") if isinstance(col, dict) else "",
                "table": t,
            })
    return matched_cols[:20]


def _verb(funcs: list[tuple[str, str]]) -> str:
    if len(funcs) == 1:
        f = funcs[0][0].lower()
        if f in ("sum", "avg", "min", "max"):
            return "the"
        return "the"
    return "the"

from __future__ import annotations

from typing import Any

SQL_GENERATION_TEMPLATE = """You are a PostgreSQL expert. Generate SQL based on the user's request using ONLY the schema below.

TABLES AND COLUMNS:
{schema_ddl}

{graph_context}

{conversation_history}
USER QUESTION: {query}

Intent: {intent_description}
Detected Tables: {tables}
Filters: {filters}
Aggregations: {aggregations}
Joins: {joins}

RULES (must follow):
1. ONLY use tables and columns listed in TABLES AND COLUMNS above
2. Never invent, guess, or hallucinate table or column names
3. For JOINs, use the relationships listed in RELATIONSHIPS above
4. Use proper PostgreSQL syntax with table aliases for JOINs
5. Return ONLY the SQL query — no explanation, no markdown, no backticks"""

SIMPLE_SQL_TEMPLATE = """Generate a PostgreSQL SQL query for: {query}

Available tables and columns:
{schema_ddl}
{graph_context}
{conversation_history}

Rules:
- Only use tables listed above
- Never invent column or table names
- Use table relationships for JOINs
- Return ONLY the SQL query, nothing else"""

REFLECTION_TEMPLATE = """Review this PostgreSQL SQL query for correctness against the schema.

SQL: {sql}

User Request: {query}

Schema:
{schema_ddl}

Check:
1. All table names must exist in the schema above
2. All column names must exist in their respective tables
3. JOIN conditions must use columns that exist in both tables
4. WHERE clause must reference valid columns
5. Functions (COUNT, SUM, AVG) must reference valid columns

If the SQL is correct, respond with "VALID".
If issues exist, list them and provide the corrected SQL."""

TEMPLATES: dict[str, str] = {
    "simple": SIMPLE_SQL_TEMPLATE,
    "standard": SQL_GENERATION_TEMPLATE,
    "reflection": REFLECTION_TEMPLATE,
}


def format_schema_ddl(tables: list[dict[str, Any]], columns: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    tbl_map = {t.get("name", "").lower(): t for t in tables}
    for tbl_name, tbl in sorted(tbl_map.items()):
        display_name = tbl.get("name", tbl_name)
        tbl_desc = tbl.get("description", "")
        tbl_cols = [c for c in columns if c.get("table_name", "").lower() == tbl_name]
        desc_line = f" -- {tbl_desc}" if tbl_desc else ""
        lines.append(f"TABLE {display_name}{desc_line}")
        lines.append(f"(")
        for col in tbl_cols:
            col_name = col.get("name", col.get("column", ""))
            col_type = col.get("data_type", col.get("type", "unknown"))
            col_desc = col.get("description", "")
            pk = " PK" if col.get("is_primary_key", col.get("primary_key", False)) else ""
            nullable = "" if col.get("is_nullable", True) else " NOT NULL"
            fk = ""
            for rel in relationships:
                if rel.get("source_column", "").lower() == col_name.lower() and rel.get("source_table", "").lower() == tbl_name:
                    fk = f" FK->{rel['target_table']}({rel['target_column']})"
                elif rel.get("target_column", "").lower() == col_name.lower() and rel.get("target_table", "").lower() == tbl_name:
                    fk = f" FK<-{rel['source_table']}({rel['source_column']})"
            desc = f" -- {col_desc}" if col_desc else ""
            lines.append(f"  {col_name} {col_type}{pk}{nullable}{fk}{desc}")
        lines.append(f")")

        # Sample rows
        sample = tbl.get("sample_rows", [])
        if sample:
            col_names = list(sample[0].keys())
            lines.append(f"SAMPLE ROWS ({len(sample)} rows):")
            for row in sample:
                vals = []
                for cn in col_names:
                    v = row.get(cn, "")
                    if v is None:
                        vals.append("NULL")
                    else:
                        vals.append(str(v)[:30])
                lines.append(f"  {', '.join(vals)}")
            lines.append("")

    return "\n".join(lines)


def format_intent_description(intent: dict[str, Any]) -> str:
    qtype = intent.get("query_type", "UNKNOWN")
    complexity = intent.get("complexity", "simple")
    return f"{qtype} query ({complexity} complexity)"

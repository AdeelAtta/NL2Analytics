from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from schema_intelligence.annotators.base import (
    AnnotatedColumn,
    AnnotationResult,
    BaseAnnotator,
)
from schema_intelligence.connectors.base import ExtractedTable

logger = logging.getLogger(__name__)


class LLMAnnotator(BaseAnnotator):
    def __init__(
        self,
        endpoint: str = "http://localhost:8000/v1",
        model: str = "qwen2.5-72b",
        api_key: str | None = None,
        timeout_seconds: int = 60,
        max_retries: int = 2,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    async def annotate(self, table: ExtractedTable) -> AnnotationResult:
        prompt = self._build_prompt(table)
        response = await self._call_llm(prompt)
        return self._parse_response(table.name, response)

    async def annotate_batch(
        self, tables: list[ExtractedTable]
    ) -> list[AnnotationResult]:
        prompt = self._build_batch_prompt(tables)
        response = await self._call_llm(prompt)
        return self._parse_batch_response(tables, response)

    def _build_prompt(self, table: ExtractedTable) -> str:
        cols_lines: list[str] = []
        for c in table.columns:
            parts = [f"  - {c.name} ({c.data_type})"]
            if c.is_primary_key:
                parts[0] += " [PK]"
            if not c.is_nullable:
                parts[0] += " [NOT NULL]"
            if c.foreign_key:
                parts[0] += f" -> {c.foreign_key.ref_table}.{c.foreign_key.ref_column}"
            if c.default_value is not None:
                parts[0] += f" DEFAULT {c.default_value}"
            cols_lines.append(parts[0])

        cols_str = "\n".join(cols_lines)

        return f"""<schema>
Table: {table.name}
Columns:
{cols_str}
</schema>

Generate a concise JSON response with:
1. "table_description": A 1-2 sentence description of what this table stores.
2. "columns": An array of {{"name": "<column_name>", "description": "<one sentence description>"}} for each column.

Return ONLY valid JSON, no other text."""

    def _build_batch_prompt(self, tables: list[ExtractedTable]) -> str:
        sections: list[str] = []
        for table in tables:
            cols_lines: list[str] = []
            for c in table.columns:
                parts = [f"  - {c.name} ({c.data_type})"]
                if c.is_primary_key:
                    parts[0] += " [PK]"
                if not c.is_nullable:
                    parts[0] += " [NOT NULL]"
                if c.foreign_key:
                    parts[0] += f" -> {c.foreign_key.ref_table}.{c.foreign_key.ref_column}"
                if c.default_value is not None:
                    parts[0] += f" DEFAULT {c.default_value}"
                cols_lines.append(parts[0])
            sections.append(
                f"---\nTable: {table.name}\nColumns:\n" + "\n".join(cols_lines)
            )

        return (
            "\n".join(sections)
            + """

For each table above, generate a JSON object with:
1. "table_description": A 1-2 sentence description of what this table stores.
2. "columns": An array of {"name": "<column_name>", "description": "<one sentence description>"} for each column.

Return ONLY a JSON array where each element corresponds to a table in order. No other text."""
        )

    async def _call_llm(self, prompt: str) -> dict[str, Any]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        body = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a database schema annotator that generates precise, concise descriptions.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(
                        f"{self._endpoint}/chat/completions",
                        headers=headers,
                        json=body,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    cleaned = content.strip()
                    if cleaned.startswith("```"):
                        cleaned = cleaned.split("\n", 1)[-1]
                        cleaned = cleaned.rsplit("```", 1)[0]
                    return json.loads(cleaned)
            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM call attempt %d failed: %s", attempt + 1, e
                )

        msg = f"LLM annotator failed after {self._max_retries + 1} attempts"
        raise RuntimeError(msg) from last_error

    def _parse_response(
        self, table_name: str, response: dict[str, Any]
    ) -> AnnotationResult:
        table_desc = response.get("table_description", "")
        raw_cols = response.get("columns", [])
        columns = [
            AnnotatedColumn(
                name=c["name"],
                description=c.get("description", ""),
            )
            for c in raw_cols
        ]
        return AnnotationResult(
            table_name=table_name,
            table_description=table_desc,
            columns=columns,
        )

    def _parse_batch_response(
        self, tables: list[ExtractedTable], response: Any
    ) -> list[AnnotationResult]:
        if isinstance(response, dict):
            return [self._parse_response(t.name, response) for t in tables]
        if isinstance(response, list):
            results: list[AnnotationResult] = []
            for table, item in zip(tables, response, strict=False):
                if isinstance(item, dict):
                    results.append(self._parse_response(table.name, item))
                else:
                    results.append(
                        AnnotationResult(
                            table_name=table.name,
                            table_description="",
                            columns=[
                                AnnotatedColumn(name=c.name, description="")
                                for c in table.columns
                            ],
                        )
                    )
            return results
        return [
            AnnotationResult(
                table_name=t.name,
                table_description="",
                columns=[AnnotatedColumn(name=c.name, description="") for c in t.columns],
            )
            for t in tables
        ]

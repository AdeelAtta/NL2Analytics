from __future__ import annotations

import time
import uuid
from typing import Any

from sqlglot import exp as E  # noqa: N812

from ke.models.generation import (
    CandidateResult,
    GenerationResult,
    GenerationStatus,
    ReflectionResult,
)
from ke.models.planning import (
    ModelTier,
    QueryIntent,
    QueryType,
)
from ke.services.inference import InferenceFactory, ModelClient
from ke.services.prompts import TEMPLATES, format_intent_description, format_schema_ddl
from ke.services.router import ModelRouter

_SAFE_OPS = {"=", "!=", "<>", "<", ">", "<=", ">=", "LIKE", "ILIKE", "IN", "NOT IN", "IS", "IS NOT"}


def _safe_quote(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _safe_identifier(name: str) -> str:
    return E.to_identifier(name).sql(dialect="postgres")


def _safe_operator(op: str) -> str:
    upper = op.upper().strip()
    return upper if upper in _SAFE_OPS else "="


class NL2SQLGenerator:
    def __init__(self, model_router: ModelRouter | None = None) -> None:
        self._router = model_router or ModelRouter()

    async def generate(
        self,
        query: str,
        intent: QueryIntent | dict[str, Any],
        context: dict[str, Any] | None = None,
        tenant_tier: str = "pro",
        num_candidates: int = 1,
        reflect: bool = True,
        dialect: str = "postgresql",
    ) -> GenerationResult:
        start = time.perf_counter()
        gen_id = str(uuid.uuid4())

        if isinstance(intent, dict):
            intent = QueryIntent(**intent)

        if intent.query_type == QueryType.DDL:
            return GenerationResult(
                id=gen_id,
                query=query,
                sql="",
                status=GenerationStatus.FAILED,
                model_tier="none",
                model_name="",
                intent=intent.model_dump() if isinstance(intent, QueryIntent) else intent,
                error="DDL operations are not supported",
                latency_ms=(time.perf_counter() - start) * 1000,
            )

        route = self._router.route(intent, tenant_tier)
        selected_tier = route["selected_tier"]
        config = route["config"]
        fallback_chain = route["fallback_chain"]

        if selected_tier == ModelTier.NONE.value:
            return GenerationResult(
                id=gen_id, query=query, sql="",
                status=GenerationStatus.FAILED,
                model_tier="none", model_name="",
                intent=intent.model_dump() if isinstance(intent, QueryIntent) else intent,
                error="Rule-based generation is disabled. Configure an LLM provider.",
                latency_ms=0.0, cost=0.0,
            )
            elapsed = (time.perf_counter() - start) * 1000
            return GenerationResult(
                id=gen_id,
                query=query,
                sql=sql,
                status=GenerationStatus.COMPLETED,
                model_tier=ModelTier.NONE.value,
                model_name="rule_based",
                intent=intent.model_dump() if isinstance(intent, QueryIntent) else intent,
                candidates=[CandidateResult(sql=sql, model_tier=ModelTier.NONE.value, model_name="rule_based", score=1.0, latency_ms=elapsed)],
                latency_ms=elapsed,
                cost=0.0,
            )

        candidates: list[CandidateResult] = []
        last_error: str | None = None

        for tier_name in reversed(fallback_chain):
            if tier_name == ModelTier.NONE.value:
                continue
            tier_config = ModelRouter.TIER_CONFIGS.get(ModelTier(tier_name), {})
            provider = tier_config.get("provider", "mock")
            model_name = tier_config.get("model", "mock")
            cost_per_query = tier_config.get("cost_per_query", 0.0)

            try:
                client = InferenceFactory.create(provider, model_name, cost_per_query)
                for _ in range(num_candidates):
                    candidate_start = time.perf_counter()
                    schema_ddl = format_schema_ddl(
                        context.get("tables", []) if context else [],
                        context.get("columns", []) if context else [],
                        context.get("relationships", []) if context else [],
                    )
                    prompt = self._build_prompt(query, intent, context, schema_ddl, dialect, tier_name)
                    import logging
                    logging.getLogger("ke.prompt").info("LLM Prompt:\n%s\n---END PROMPT---", prompt)
                    sql = await client.generate(prompt)
                    candidate_elapsed = (time.perf_counter() - candidate_start) * 1000
                    score = self._score_candidate(sql, query, intent)
                    candidates.append(CandidateResult(
                        sql=sql,
                        model_tier=tier_name,
                        model_name=client.model_name,
                        score=score,
                        latency_ms=candidate_elapsed,
                        cost=cost_per_query,
                    ))
                break
            except Exception as e:
                last_error = str(e)
                continue

        if not candidates:
            elapsed = (time.perf_counter() - start) * 1000
            return GenerationResult(
                id=gen_id, query=query, sql="",
                status=GenerationStatus.FAILED,
                model_tier="none", model_name="",
                intent=intent.model_dump() if isinstance(intent, QueryIntent) else intent,
                error=f"No LLM model available. All model tiers failed. "
                      f"Configure HF_TOKEN or OPENAI_API_KEY. Last error: {last_error or 'unknown'}",
                latency_ms=elapsed, cost=0.0,
            )

        best = max(candidates, key=lambda c: c.score)
        sql = best.sql

        reflection: ReflectionResult | None = None
        if reflect:
            reflection = await self._reflect(query, sql, context, dialect)
            if reflection and not reflection.is_valid and reflection.suggestion:
                sql = reflection.suggestion

        elapsed = (time.perf_counter() - start) * 1000
        total_cost = sum(c.cost for c in candidates)

        return GenerationResult(
            id=gen_id,
            query=query,
            sql=sql,
            status=GenerationStatus.COMPLETED if not last_error else GenerationStatus.FAILED,
            model_tier=best.model_tier,
            model_name=best.model_name,
            intent=intent.model_dump() if isinstance(intent, QueryIntent) else intent,
            candidates=candidates,
            reflection=reflection,
            latency_ms=elapsed,
            cost=total_cost,
        )

    def _build_prompt(
        self,
        query: str,
        intent: QueryIntent,
        context: dict[str, Any] | None,
        schema_ddl: str,
        dialect: str,
        tier: str,
    ) -> str:
        template = TEMPLATES.get("standard", TEMPLATES["simple"])
        tables_str = ", ".join(t.name for t in intent.tables) if intent.tables else "N/A"
        filters_str = "; ".join(f"{f.column.column} {f.operator} {f.value}" for f in intent.filters) if intent.filters else "None"
        aggs_str = "; ".join(f"{a.get('function', '')}({a.get('column', '')})" for a in intent.aggregations) if intent.aggregations else "None"
        joins_str = "; ".join(f"{j.get('source_table', '')}.{j.get('source_column', '')} = {j.get('target_table', '')}.{j.get('target_column', '')}" for j in intent.join_edges) if intent.join_edges else "None"
        intent_desc = format_intent_description(intent.model_dump())
        conversation_history = context.get("conversation_history", "") if context else ""
        graph_context = context.get("graph_context", "") if context else ""
        return template.format(
            dialect=dialect,
            schema_ddl=schema_ddl or "No schema available",
            graph_context=graph_context,
            conversation_history=conversation_history + "\n" if conversation_history else "",
            query=query,
            intent_description=intent_desc,
            tables=tables_str,
            filters=filters_str,
            aggregations=aggs_str,
            joins=joins_str,
        )

    async def _reflect(self, query: str, sql: str, context: dict[str, Any] | None, dialect: str) -> ReflectionResult | None:
        try:
            schema_ddl = format_schema_ddl(
                context.get("tables", []) if context else [],
                context.get("columns", []) if context else [],
                context.get("relationships", []) if context else [],
            )
            prompt = TEMPLATES["reflection"].format(dialect=dialect, sql=sql, query=query, schema_ddl=schema_ddl or "N/A")
            client: ModelClient = MockClient("reflection")
            result = await client.generate(prompt)
            if "VALID" in result.upper() and "ISSUE" not in result.upper():
                return ReflectionResult(is_valid=True)
            suggestion = ""
            lines = result.split("\n")
            sql_lines = [l for l in lines if l.strip().upper().startswith(("SELECT", "WITH", "INSERT", "UPDATE", "DELETE"))]
            if sql_lines:
                suggestion = "\n".join(sql_lines)
            issues = [l.strip() for l in lines if l.strip().startswith("-") or l.strip().startswith("*")]
            return ReflectionResult(is_valid=False, issues=issues or ["Reflection found issues"], suggestion=suggestion)
        except Exception:
            return None

    def _rule_based_generate(self, query: str, intent: QueryIntent, context: dict[str, Any] | None, dialect: str) -> str:
        import re as _re

        tables = intent.tables
        if not tables:
            words = _re.findall(r"\b[a-z]{3,}\b", query.lower())
            stopwords = {"the", "and", "for", "all", "from", "with", "that", "this", "show", "list", "get", "find", "display", "give", "me", "each", "per", "how", "many", "what", "which", "where", "have", "has", "who", "over", "under", "more", "less", "than", "greater", "higher", "lower", "total", "average", "minimum", "maximum", "number", "count", "sum", "who", "is", "are", "were", "was", "been", "being", "does", "do", "did", "will", "would", "could", "should", "may", "might", "can", "shall"}
            candidates = sorted(set(w for w in words if w not in stopwords), key=len, reverse=True)

            if context and context.get("tables"):
                known_tables = {t["name"].lower(): t["name"] for t in context["tables"]}
                for cand in candidates:
                    for tbl_key, tbl_val in known_tables.items():
                        if cand in tbl_key or tbl_key in cand:
                            return f"SELECT * FROM {tbl_val};"
                    for tbl_key in known_tables:
                        if len(cand) > 3 and len(tbl_key) > 3 and (cand[:3] == tbl_key[:3]):
                            return f"SELECT * FROM {known_tables[tbl_key]};"

            if candidates:
                return f"SELECT * FROM {_safe_identifier(candidates[0])} LIMIT 10;"
            return "SELECT 1;"

        table_name = _safe_identifier(tables[0].name)
        cols = [_safe_identifier(c.column) for c in intent.columns] if intent.columns else ["*"]

        sql = f"SELECT {', '.join(cols)} FROM {table_name}"

        if intent.filters:
            filter_clauses = []
            for f in intent.filters:
                op = _safe_operator(f.operator)
                val = f.value
                col_name = _safe_identifier(f.column.column)
                if op in ("IN", "NOT IN"):
                    parts = [x.strip().strip("'\"") for x in val.split(",")]
                    quoted = ", ".join(_safe_quote(v) for v in parts)
                    filter_clauses.append(f"{col_name} {op} ({quoted})")
                elif op in ("IS", "IS NOT"):
                    val_upper = val.strip().upper()
                    if val_upper in ("NULL", "TRUE", "FALSE", "UNKNOWN"):
                        filter_clauses.append(f"{col_name} {op} {val_upper}")
                    else:
                        filter_clauses.append(f"{col_name} {op} {_safe_quote(val)}")
                else:
                    filter_clauses.append(f"{col_name} {op} {_safe_quote(val)}")
            sql += " WHERE " + " AND ".join(filter_clauses)

        has_agg = bool(intent.aggregations)
        if has_agg:
            agg_parts = []
            for a in intent.aggregations:
                func = a.get("function", "COUNT")
                col = a.get("column", "*")
                if col != "*":
                    col = _safe_identifier(col)
                agg_parts.append(f"{func}({col})")
            sql = f"SELECT {', '.join(agg_parts)} FROM {table_name}"

        if len(tables) > 1:
            join_clauses = []
            for j in intent.join_edges:
                src = _safe_identifier(j.get("source_table", tables[0].name))
                tgt = _safe_identifier(j.get("target_table", tables[1].name))
                src_col = _safe_identifier(j.get("source_column", "id"))
                tgt_col = _safe_identifier(j.get("target_column", "id"))
                join_type = j.get("join_type", "INNER")
                join_clauses.append(f"{join_type} JOIN {tgt} ON {src}.{src_col} = {tgt}.{tgt_col}")
            sql += " " + " ".join(join_clauses)

        if has_agg and intent.columns:
            group_cols = [_safe_identifier(c.column) for c in intent.columns]
            sql += " GROUP BY " + ", ".join(group_cols)

        sql += ";"
        return sql

    def _score_candidate(self, sql: str, query: str, intent: QueryIntent) -> float:
        score = 0.5
        if not sql:
            return 0.0
        keywords = _extract_keywords(query)
        sql_lower = sql.lower()
        for kw in keywords:
            if kw in sql_lower:
                score += 0.1
        if "where" in sql_lower and intent.filters:
            score += 0.2
        if "join" in sql_lower and len(intent.tables) > 1:
            score += 0.2
        if "group by" in sql_lower and intent.aggregations:
            score += 0.2
        if sql.strip().endswith(";"):
            score += 0.05
        return min(1.0, score)


def _extract_keywords(query: str) -> list[str]:
    import re
    words = re.findall(r"\b[a-z]{3,}\b", query.lower())
    stopwords = {"the", "and", "for", "all", "from", "with", "that", "this", "show", "list", "get", "find", "display", "give", "me", "each", "per", "how", "many", "what", "which", "where", "have", "has", "who"}
    return [w for w in words if w not in stopwords]

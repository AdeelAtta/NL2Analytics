from __future__ import annotations

import re
from typing import Any

from ke.models.planning import (
    ColumnRef,
    FilterExpression,
    JoinEdge,
    QueryComplexity,
    QueryIntent,
    QueryType,
    TableRef,
)


class IntentAgent:
    LEVEL1_PATTERNS: dict[QueryType, list[re.Pattern]] = {
        QueryType.AGGREGATION: [
            re.compile(r"\b(average|avg|mean|total|sum|count|minimum|min|maximum|max|number of|how many|distinct)\b", re.I),
        ],
        QueryType.WINDOW: [
            re.compile(r"\b(rank|ranking|row number|top\s+\d+|bottom\s+\d+|running total|cumulative|moving average|percentile)\b", re.I),
        ],
        QueryType.JOIN: [
            re.compile(r"\b(join|together with|combined with)\b", re.I),
        ],
        QueryType.COMPOUND: [
            re.compile(r"\b(compared to|versus|vs|compared with|difference between)\b", re.I),
        ],
        QueryType.DDL: [
            re.compile(r"\b(create|alter|drop|insert|update|delete|truncate)\b", re.I),
        ],
        QueryType.FILTERED_SELECT: [
            re.compile(r"\b(where|find|filter|search for|with|having)\b", re.I),
        ],
        QueryType.SUBQUERY: [
            re.compile(r"\b(than average|than the average|above.verage|below.verage|who have|that have|which have)\b", re.I),
        ],
        QueryType.CROSS_DB: [
            re.compile(r"\b(compared to|across databases|from both|vs\b)", re.I),
        ],
        QueryType.ANALYTICAL: [
            re.compile(r"\b(trend|growth|decline|seasonal|forecast|rollup|cube|pivot|olap)\b", re.I),
        ],
    }

    def classify(self, query: str, context: dict[str, Any] | None = None) -> QueryIntent:
        query_lower = query.lower()
        scores: dict[QueryType, float] = {}

        for qtype, patterns in self.LEVEL1_PATTERNS.items():
            matches = sum(1 for p in patterns if p.search(query_lower))
            if matches > 0:
                scores[qtype] = min(1.0, matches * 0.35 + 0.2)

        if QueryType.DDL in scores:
            return QueryIntent(
                query_type=QueryType.DDL,
                complexity=QueryComplexity.SIMPLE,
                confidence=0.0,
                description="DDL operations are not supported in MVP",
            )

        tables = self._extract_tables(query, context)
        columns = self._extract_columns(query, context)
        filters = self._extract_filters(query, context)
        join_edges = self._extract_join_edges(tables, context)
        aggregations = self._extract_aggregations(query, context)

        table_count = len(tables)
        if table_count > 4:
            scores[QueryType.JOIN] = max(scores.get(QueryType.JOIN, 0), 0.6)
        if table_count > 6:
            scores[QueryType.COMPOUND] = max(scores.get(QueryType.COMPOUND, 0), 0.5)

        has_cross_db = self._detect_cross_db(tables, context)
        if has_cross_db:
            scores[QueryType.CROSS_DB] = max(scores.get(QueryType.CROSS_DB, 0), 0.7)

        best_type, best_score = self._select_best(scores)

        if best_type is None or best_score < 0.4:
            if table_count >= 2:
                best_type = QueryType.JOIN
                best_score = 0.6
            elif table_count == 1 and filters:
                best_type = QueryType.FILTERED_SELECT
                best_score = 0.7
            elif table_count == 1 and not filters:
                best_type = QueryType.SIMPLE_SELECT
                best_score = 0.9
            elif _has_content_words(query):
                best_type = QueryType.SIMPLE_SELECT
                best_score = 0.5
                if _suggests_join(query):
                    best_type = QueryType.JOIN
                    best_score = 0.4
            else:
                best_type = QueryType.UNKNOWN
                best_score = 0.0

        complexity = self._compute_complexity(best_type, table_count, aggregations)

        model_tier = self._select_model_tier(complexity)

        return QueryIntent(
            query_type=best_type,
            complexity=complexity,
            confidence=best_score,
            tables=tables,
            columns=columns,
            filters=filters,
            join_edges=join_edges,
            aggregations=aggregations,
            model_tier=model_tier,
            description=f"{best_type.value} query with {table_count} table(s)",
        )

    def _select_best(self, scores: dict[QueryType, float]) -> tuple[QueryType | None, float]:
        if not scores:
            return None, 0.0
        best = max(scores, key=scores.get)
        return best, scores[best]

    def _compute_complexity(self, qtype: QueryType, table_count: int, aggregations: list) -> QueryComplexity:
        if qtype in (QueryType.UNKNOWN, QueryType.DDL):
            return QueryComplexity.SIMPLE
        if qtype in (QueryType.CROSS_DB, QueryType.ANALYTICAL):
            return QueryComplexity.VERY_COMPLEX
        if qtype in (QueryType.COMPOUND, QueryType.SUBQUERY, QueryType.WINDOW):
            return QueryComplexity.COMPLEX
        if qtype in (QueryType.JOIN, QueryType.AGGREGATION):
            if table_count > 4:
                return QueryComplexity.COMPLEX
            if table_count > 2:
                return QueryComplexity.MEDIUM
            return QueryComplexity.SIMPLE
        if qtype in (QueryType.FILTERED_SELECT, QueryType.SIMPLE_SELECT):
            if table_count > 2:
                return QueryComplexity.MEDIUM
            return QueryComplexity.SIMPLE
        return QueryComplexity.SIMPLE

    def _select_model_tier(self, complexity: QueryComplexity) -> str:
        mapping = {
            QueryComplexity.SIMPLE: "none",
            QueryComplexity.MEDIUM: "lightweight",
            QueryComplexity.COMPLEX: "standard",
            QueryComplexity.VERY_COMPLEX: "premium",
        }
        return mapping[complexity]

    def _extract_tables(self, query: str, context: dict[str, Any] | None) -> list[TableRef]:
        tables: list[TableRef] = []
        if not context:
            return tables
        context_tables = context.get("tables", [])
        if not context_tables:
            return tables
        query_lower = query.lower()
        for ctx_table in context_tables:
            name = ctx_table.get("name", "") if isinstance(ctx_table, dict) else getattr(ctx_table, "name", "")
            if name and (name.lower() in query_lower or _word_in_query(name, query_lower)):
                tid = ctx_table.get("id", "") if isinstance(ctx_table, dict) else getattr(ctx_table, "id", "")
                tables.append(TableRef(id=tid, name=name))
        return tables

    def _extract_columns(self, query: str, context: dict[str, Any] | None) -> list[ColumnRef]:
        columns: list[ColumnRef] = []
        if not context:
            return columns
        context_columns = context.get("columns", [])
        query_lower = query.lower()
        for ctx_col in context_columns:
            name = ctx_col.get("name", "") if isinstance(ctx_col, dict) else getattr(ctx_col, "name", "")
            table_name = ctx_col.get("table_name", "") if isinstance(ctx_col, dict) else getattr(ctx_col, "table_name", "")
            if name and name.lower() in query_lower:
                columns.append(ColumnRef(table=table_name, column=name))
        return columns

    def _extract_filters(self, query: str, context: dict[str, Any] | None) -> list[FilterExpression]:
        filters: list[FilterExpression] = []
        ql = query.lower()
        date_pattern = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
        dates = date_pattern.findall(query)

        if not context:
            return filters

        columns = context.get("columns", [])
        col_names = {}
        for c in columns:
            n = c.get("name", "").lower() if isinstance(c, dict) else getattr(c, "name", "").lower()
            t = c.get("table_name", "") if isinstance(c, dict) else getattr(c, "table_name", "")
            d = c.get("data_type", "") if isinstance(c, dict) else getattr(c, "data_type", "")
            col_names[n] = {"table": t, "type": d}

        if dates:
            for cname, info in col_names.items():
                if any(t in info["type"].lower() for t in ("date", "time", "timestamp")):
                    filters.append(FilterExpression(
                        column=ColumnRef(table=info["table"], column=cname),
                        operator="BETWEEN",
                        value=f"{dates[0][0]}-{dates[0][1]}-{dates[0][2]}",
                    ))
                    break

        status_keywords = {"active", "inactive", "pending", "completed", "shipped", "cancelled", "deleted"}
        status_cols = {n for n in col_names if n in ("status", "state")}
        for word in ql.split():
            clean = word.strip(",.!?\"';:")
            if clean in status_keywords and status_cols:
                for sc in status_cols:
                    info = col_names[sc]
                    filters.append(FilterExpression(
                        column=ColumnRef(table=info["table"], column=sc),
                        operator="=",
                        value=clean,
                    ))
                    break
                break

        date_phrases = {"yesterday", "today", "last month", "this month", "last week", "this week", "last year", "this year"}
        date_cols = {n for n, info in col_names.items() if any(t in info["type"].lower() for t in ("date", "time", "timestamp"))}
        for phrase in date_phrases:
            if phrase in ql and date_cols:
                for dc in date_cols:
                    info = col_names[dc]
                    filters.append(FilterExpression(
                        column=ColumnRef(table=info["table"], column=dc),
                        operator="=",
                        value=phrase,
                    ))
                    break
                break

        location_keywords = {"from", "in", "at"}
        date_related = {"yesterday", "today", "last", "this", "next", "previous", "month", "week", "year", "quarter"}
        words = ql.split()
        for i, w in enumerate(words):
            if w in location_keywords and i + 1 < len(words):
                if w in ("in",) and i + 1 < len(words) and words[i + 1] in ("each", "the", "every", "all"):
                    continue
                pieces = []
                for j in range(i + 1, len(words)):
                    if words[j] in date_related:
                        break
                    if words[j] in ("in", "of", "by", "for"):
                        break
                    pieces.append(words[j].strip(",.!?\"';:"))
                if pieces:
                    city_val = " ".join(pieces)
                    city_cols = {n for n in col_names if n in ("city", "location", "state", "region")}
                    if city_cols and len(city_val) > 1:
                        for cc in city_cols:
                            info = col_names[cc]
                            filters.append(FilterExpression(
                                column=ColumnRef(table=info["table"], column=cc),
                                operator="=",
                                value=city_val,
                            ))
                            break
                        break

        numeric_ops = [
            ({"over", "more than", "greater than", "above", "exceeds", "exceeding", "higher than"}, ">"),
            ({"under", "less than", "below", "lower than", "fewer than"}, "<"),
            ({"at least", "minimum", "no less than"}, ">="),
            ({"at most", "maximum", "no more than"}, "<="),
            ({"equals", "equal to", "exactly"}, "="),
        ]
        for keywords, operator in numeric_ops:
            for kw in keywords:
                idx = ql.find(kw)
                if idx >= 0:
                    after = ql[idx + len(kw):].strip().split()[0] if ql[idx + len(kw):].strip() else ""
                    try:
                        val = int(after.replace(",", ""))
                        before = ql[:idx].strip().split()[-1] if ql[:idx].strip() else ""

                        # Find tables matching the word before the operator
                        table_names_in_ctx = {t.get("name", "").lower() for t in (context.get("tables") or [])}
                        matched_table = before if before in table_names_in_ctx else ""

                        all_numeric = {n: info for n, info in col_names.items()
                                       if any(t in info["type"].lower() for t in ("int", "decimal", "numeric", "float", "double", "bigint"))}

                        if matched_table:
                            preferred = {n: info for n, info in all_numeric.items()
                                         if info["table"].lower() == matched_table}
                            if preferred:
                                candidates = sorted(preferred.keys(),
                                    key=lambda c: 1 if c.endswith("_id") or c == "id" else 0)
                                for nc in candidates:
                                    info = preferred[nc]
                                    filters.append(FilterExpression(
                                        column=ColumnRef(table=info["table"], column=nc),
                                        operator=operator, value=str(val),
                                    ))
                                    break
                                break

                        if not filters and all_numeric:
                            candidates = sorted(all_numeric.keys(),
                                key=lambda c: (0 if before and before in c else 1,
                                               1 if c.endswith("_id") else 0,
                                               c != "id"))
                            for nc in candidates:
                                info = all_numeric[nc]
                                filters.append(FilterExpression(
                                    column=ColumnRef(table=info["table"], column=nc),
                                    operator=operator, value=str(val),
                                ))
                                break
                            break
                    except (ValueError, IndexError):
                        pass
            if filters:
                break

        stock_phrases = {"out of stock", "low stock", "in stock"}
        for phrase in stock_phrases:
            if phrase in ql:
                stock_cols = {n for n in col_names if "stock" in n or n == "quantity"}
                if stock_cols:
                    for sc in stock_cols:
                        info = col_names[sc]
                        filters.append(FilterExpression(
                            column=ColumnRef(table=info["table"], column=sc),
                            operator="=",
                            value="0" if "out of" in phrase else "0",
                        ))
                        break
                    break

        return filters

    def _extract_join_edges(self, tables: list[TableRef], context: dict[str, Any] | None) -> list[dict]:
        edges: list[dict] = []
        if len(tables) < 2 or not context:
            return edges
        relationships = context.get("relationships", [])
        table_ids = {t.id for t in tables}
        table_name_set = {t.name.lower() for t in tables}
        for rel in relationships:
            src_id = rel.get("source_table_id", "") if isinstance(rel, dict) else getattr(rel, "source_table_id", "")
            tgt_id = rel.get("target_table_id", "") if isinstance(rel, dict) else getattr(rel, "target_table_id", "")
            src_name = (rel.get("source_table", "") if isinstance(rel, dict) else getattr(rel, "source_table", "")).lower()
            tgt_name = (rel.get("target_table", "") if isinstance(rel, dict) else getattr(rel, "target_table", "")).lower()

            if src_id in table_ids or tgt_id in table_ids or src_name in table_name_set or tgt_name in table_name_set:
                src_col = rel.get("source_column", "") if isinstance(rel, dict) else getattr(rel, "source_column", "")
                tgt_col = rel.get("target_column", "") if isinstance(rel, dict) else getattr(rel, "target_column", "")

                if not src_name or src_name not in table_name_set:
                    src_name = _table_name_by_id(src_id, tables).lower()
                if not tgt_name or tgt_name not in table_name_set:
                    tgt_name = _table_name_by_id(tgt_id, tables).lower()

                confidence = rel.get("confidence", 1.0) if isinstance(rel, dict) else getattr(rel, "confidence", 1.0)
                edges.append({
                    "source_table": src_name,
                    "source_column": src_col,
                    "target_table": tgt_name,
                    "target_column": tgt_col,
                    "join_type": "INNER",
                    "confidence": float(confidence),
                })
        if not edges and len(tables) >= 2:
            for i in range(len(tables) - 1):
                edges.append({
                    "source_table": tables[i].name,
                    "source_column": "",
                    "target_table": tables[i + 1].name,
                    "target_column": "",
                    "join_type": "INNER",
                    "confidence": 0.3,
                })
        return edges

    def _extract_aggregations(self, query: str, context: dict[str, Any] | None) -> list:
        query_lower = query.lower()
        aggs = []
        agg_patterns = [
            (r"\b(sum|total)\s+(\w+)", "SUM"),
            (r"\b(average|avg|mean)\s+(\w+)", "AVG"),
            (r"\b(count|number of)\s+(\w+)", "COUNT"),
            (r"\b(min|minimum|smallest|lowest)\s+(\w+)", "MIN"),
            (r"\b(max|maximum|largest|highest)\s+(\w+)", "MAX"),
        ]
        for pattern, func in agg_patterns:
            m = re.search(pattern, query_lower)
            if m:
                col_name = m.group(2)
                aggs.append({"function": func, "column": col_name})
        return aggs

    def _detect_cross_db(self, tables: list[TableRef], context: dict[str, Any] | None) -> bool:
        if len(tables) < 2 or not context:
            return False
        databases = set()
        for t in tables:
            if t.database_name:
                databases.add(t.database_name)
        return len(databases) > 1


def _has_content_words(query: str) -> bool:
    words = re.findall(r'\b[a-z]{3,}\b', query.lower())
    return len(words) >= 2


def _suggests_join(query: str) -> bool:
    q = query.lower()
    return any(w in q for w in ("with", "and", "for each", "per"))


def _word_in_query(word: str, query: str) -> bool:
    pattern = re.compile(r"\b" + re.escape(word.lower()) + r"\b")
    return bool(pattern.search(query))


def _table_name_by_id(table_id: str, tables: list[TableRef]) -> str:
    for t in tables:
        if t.id == table_id:
            return t.name
    return table_id

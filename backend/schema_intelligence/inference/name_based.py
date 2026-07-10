from __future__ import annotations

import re
from collections import defaultdict
from typing import ClassVar

from schema_intelligence.connectors.base import ExtractedColumn, ExtractedTable
from schema_intelligence.inference.base import (
    BaseInferenceEngine,
    InferenceContext,
    InferredRelationship,
)


class NameBasedInferenceEngine(BaseInferenceEngine):
    _EXISTING_FK_PAIRS: ClassVar[set[tuple[str, str, str, str]]] = set()

    def infer(self, context: InferenceContext) -> list[InferredRelationship]:
        self._build_existing_fk_set(context.tables)
        results: list[InferredRelationship] = []
        results.extend(self._strategy_naming_heuristic(context))
        results.extend(self._strategy_reverse_naming(context))
        results.extend(self._strategy_overlap(context))
        results.extend(self._detect_junction_tables(context))
        results.extend(self._detect_self_references(context))
        results = self._score_fusion(results, context)
        results = self._deduplicate(results)
        results = self._filter_by_threshold(results, context.min_confidence)
        return results

    def _build_existing_fk_set(self, tables: list[ExtractedTable]) -> None:
        NameBasedInferenceEngine._EXISTING_FK_PAIRS.clear()
        for table in tables:
            for col in table.columns:
                if col.foreign_key is not None:
                    NameBasedInferenceEngine._EXISTING_FK_PAIRS.add(
                        (table.name, col.name, col.foreign_key.ref_table, col.foreign_key.ref_column)
                    )

    def _strategy_naming_heuristic(
        self, context: InferenceContext
    ) -> list[InferredRelationship]:
        results: list[InferredRelationship] = []
        table_names = {t.name for t in context.tables}
        table_map = {t.name: t for t in context.tables}
        for table in context.tables:
            for col in table.columns:
                match = re.match(r"^(.+)_id$", col.name, re.I)
                if not match:
                    continue
                target_name = match.group(1)
                candidates = {tn for tn in table_names if _singularize(tn) == _singularize(target_name) or tn.lower() == target_name.lower()}
                if not candidates:
                    continue
                target_name = min(candidates, key=len)
                if not _has_id_column(table_map[target_name]):
                    continue
                if self._is_existing_fk(table.name, col.name, target_name, "id"):
                    continue
                results.append(
                    InferredRelationship(
                        source_table=table.name,
                        source_column=col.name,
                        target_table=target_name,
                        target_column="id",
                        confidence=context.naming_confidence,
                        strategy="naming_heuristic",
                        relationship_type="inferred",
                    )
                )
        return results

    def _strategy_reverse_naming(
        self, context: InferenceContext
    ) -> list[InferredRelationship]:
        results: list[InferredRelationship] = []
        table_names = {t.name for t in context.tables}
        table_map = {t.name: t for t in context.tables}

        for table_a in context.tables:
            id_cols = [c for c in table_a.columns if c.name.lower() == "id"]
            if not id_cols:
                continue
            for table_b in context.tables:
                if table_b.name == table_a.name:
                    continue
                singular = _singularize(table_a.name)
                target_pattern = re.compile(
                    rf"^({re.escape(singular)}|{re.escape(table_a.name)})_id$", re.I
                )
                for col_b in table_b.columns:
                    if not target_pattern.match(col_b.name):
                        continue
                    if self._is_existing_fk(
                        table_b.name, col_b.name, table_a.name, "id"
                    ):
                        continue
                    results.append(
                        InferredRelationship(
                            source_table=table_b.name,
                            source_column=col_b.name,
                            target_table=table_a.name,
                            target_column="id",
                            confidence=context.reverse_naming_confidence,
                            strategy="reverse_naming",
                            relationship_type="inferred",
                        )
                    )
        return results

    def _strategy_overlap(
        self, context: InferenceContext
    ) -> list[InferredRelationship]:
        results: list[InferredRelationship] = []
        pk_cols_by_table: dict[str, list[ExtractedColumn]] = defaultdict(list)
        for table in context.tables:
            for col in table.columns:
                if col.is_primary_key and _is_integer_type(col.data_type):
                    pk_cols_by_table[table.name].append(col)

        for i, table_a in enumerate(context.tables):
            for col_a in table_a.columns:
                if col_a.foreign_key is not None:
                    continue
                if col_a.name.lower() == "id":
                    continue
                if not col_a.name.endswith("_id"):
                    continue
                base = col_a.name[:-3]
                for table_b, pk_cols in pk_cols_by_table.items():
                    if table_b == table_a.name:
                        continue
                    for pk_col in pk_cols:
                        if pk_col.name.lower() != "id":
                            continue
                        if base.lower() == table_b.lower():
                            continue
                        if _singularize(base) == table_b:
                            continue
                        if not _is_compatible_type(col_a.data_type, pk_col.data_type):
                            continue
                        if self._is_existing_fk(
                            table_a.name, col_a.name, table_b, pk_col.name
                        ):
                            continue
                        results.append(
                            InferredRelationship(
                                source_table=table_a.name,
                                source_column=col_a.name,
                                target_table=table_b,
                                target_column=pk_col.name,
                                confidence=context.overlap_confidence,
                                strategy="name_type_overlap",
                                relationship_type="inferred",
                            )
                        )
        return results

    def _detect_junction_tables(
        self, context: InferenceContext
    ) -> list[InferredRelationship]:
        results: list[InferredRelationship] = []
        table_names_lower = {t.name.lower() for t in context.tables}
        table_map = {t.name: t for t in context.tables}
        for table in context.tables:
            if len(table.columns) < 2:
                continue
            pk_cols = [c for c in table.columns if c.is_primary_key]
            if len(pk_cols) < 2:
                continue
            fk_candidates: list[tuple[str, str, str]] = []
            for pk_col in pk_cols:
                if pk_col.foreign_key is not None:
                    fk_candidates.append((pk_col.name, pk_col.foreign_key.ref_table, pk_col.foreign_key.ref_column))
                else:
                    match = re.match(r"^(.+)_id$", pk_col.name, re.I)
                    if match:
                        target = _singularize(match.group(1))
                        for tn in table_map:
                            if _singularize(tn.lower()) == target:
                                fk_candidates.append((pk_col.name, tn, "id"))
                                break
            if len(fk_candidates) < 2:
                continue
            for col_name, ref_table, ref_column in fk_candidates:
                results.append(
                    InferredRelationship(
                        source_table=table.name,
                        source_column=col_name,
                        target_table=ref_table,
                        target_column=ref_column,
                        confidence=context.junction_confidence,
                        strategy="junction_table",
                        relationship_type="junction",
                    )
                )
        return results

    def _detect_self_references(
        self, context: InferenceContext
    ) -> list[InferredRelationship]:
        results: list[InferredRelationship] = []
        table_names = {t.name for t in context.tables}
        for table in context.tables:
            id_cols = {c.name for c in table.columns if c.name.lower() == "id" or c.is_primary_key}
            if not id_cols:
                continue
            target_id = next(iter(id_cols))
            for col in table.columns:
                if col.foreign_key is not None:
                    continue
                if not col.name.lower().endswith("_id"):
                    continue
                match = re.match(r"^(.+)_id$", col.name, re.I)
                if not match:
                    continue
                base = _singularize(match.group(1))
                if base.lower() == table.name.lower():
                    if self._is_existing_fk(table.name, col.name, table.name, target_id):
                        continue
                    results.append(
                        InferredRelationship(
                            source_table=table.name,
                            source_column=col.name,
                            target_table=table.name,
                            target_column=target_id,
                            confidence=context.self_reference_threshold,
                            strategy="self_reference",
                            relationship_type="self_reference",
                        )
                    )
                    continue
                if base not in table_names and _is_integer_type(col.data_type):
                    if self._is_existing_fk(table.name, col.name, table.name, target_id):
                        continue
                    results.append(
                        InferredRelationship(
                            source_table=table.name,
                            source_column=col.name,
                            target_table=table.name,
                            target_column=target_id,
                            confidence=context.self_reference_threshold * 0.8,
                            strategy="self_reference",
                            relationship_type="self_reference",
                        )
                    )

        return results

    def _is_existing_fk(
        self, src_table: str, src_col: str, tgt_table: str, tgt_col: str
    ) -> bool:
        return (src_table, src_col, tgt_table, tgt_col) in NameBasedInferenceEngine._EXISTING_FK_PAIRS

    def _deduplicate(
        self, results: list[InferredRelationship]
    ) -> list[InferredRelationship]:
        seen: set[tuple[str, str, str, str]] = set()
        deduped: list[InferredRelationship] = []
        for r in results:
            key = (r.source_table, r.source_column, r.target_table, r.target_column)
            if key not in seen:
                seen.add(key)
                deduped.append(r)
            else:
                existing = [x for x in deduped if (x.source_table, x.source_column, x.target_table, x.target_column) == key]
                if existing and r.confidence > existing[0].confidence:
                    deduped.remove(existing[0])
                    deduped.append(r)
        return deduped

    def _score_fusion(
        self, results: list[InferredRelationship], ctx: InferenceContext
    ) -> list[InferredRelationship]:
        by_key: dict[tuple[str, str, str, str], list[InferredRelationship]] = defaultdict(list)
        for r in results:
            key = (r.source_table, r.source_column, r.target_table, r.target_column)
            by_key[key].append(r)

        fused: list[InferredRelationship] = []
        for key, group in by_key.items():
            if len(group) == 1:
                fused.append(group[0])
            else:
                best = max(group, key=lambda x: x.confidence)
                unique_strategies = {r.strategy for r in group}
                bonus = ctx.score_fusion_bonus * (len(unique_strategies) - 1)
                best.confidence = min(1.0, best.confidence + bonus)
                best.strategy = "+".join(sorted(unique_strategies))
                fused.append(best)
        return fused

    def _filter_by_threshold(
        self, results: list[InferredRelationship], threshold: float
    ) -> list[InferredRelationship]:
        return [r for r in results if r.confidence >= threshold]
def _singularize(word: str) -> str:
    word_lower = word.lower()
    if word_lower.endswith("ies"):
        return word_lower[:-3] + "y"
    if word_lower.endswith("ses") or word_lower.endswith("xes") or word_lower.endswith("ches") or word_lower.endswith("shes"):
        return word_lower[:-2]
    if word_lower.endswith("s") and not word_lower.endswith("ss"):
        return word_lower[:-1]
    return word_lower


def _has_id_column(table: ExtractedTable) -> bool:
    return any(c.name.lower() == "id" for c in table.columns)


def _is_integer_type(dtype: str) -> bool:
    dt = dtype.upper()
    return any(
        t in dt for t in ("INT", "SERIAL", "BIGINT", "SMALLINT", "BIGSERIAL", "SMALLSERIAL")
    )


def _is_compatible_type(t1: str, t2: str) -> bool:
    t1u = t1.upper()
    t2u = t2.upper()
    if t1u == t2u:
        return True
    int_types = {"INT", "INTEGER", "BIGINT", "SMALLINT", "SERIAL", "BIGSERIAL", "SMALLSERIAL"}
    if t1u in int_types and t2u in int_types:
        return True
    uuid_types = {"UUID"}
    if t1u in uuid_types and t2u in uuid_types:
        return True
    char_types = {"VARCHAR", "CHAR", "TEXT", "BPCHAR", "CHARACTER VARYING", "CHARACTER"}
    if t1u.startswith("VARCHAR") or t1u.startswith("CHAR") or t1u == "TEXT":
        t1_base = t1u.split("(")[0]
        t2_base = t2u.split("(")[0]
        return t1_base in char_types and t2_base in char_types
    return False

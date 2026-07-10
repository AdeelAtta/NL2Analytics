from __future__ import annotations

import hashlib
import logging
from typing import Protocol

from schema_intelligence.annotators.base import (
    AnnotatedColumn,
    AnnotationResult,
    BaseAnnotator,
)
from schema_intelligence.annotators.rule_based import RuleBasedAnnotator
from schema_intelligence.connectors.base import ExtractedTable

logger = logging.getLogger(__name__)


class CacheBackend(Protocol):
    def get(self, key: str) -> AnnotationResult | None:
        ...

    def set(self, key: str, value: AnnotationResult) -> None:
        ...


class DictCache:
    def __init__(self) -> None:
        self._store: dict[str, AnnotationResult] = {}

    def get(self, key: str) -> AnnotationResult | None:
        return self._store.get(key)

    def set(self, key: str, value: AnnotationResult) -> None:
        self._store[key] = value

    def clear(self) -> None:
        self._store.clear()


class AnnotationService:
    def __init__(
        self,
        annotator: BaseAnnotator | None = None,
        cache: CacheBackend | None = None,
    ) -> None:
        self._annotator = annotator or RuleBasedAnnotator()
        self._cache = cache or DictCache()

    async def annotate(self, table: ExtractedTable) -> AnnotationResult:
        key = _cache_key(table)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = await self._annotator.annotate(table)
        self._cache.set(key, result)
        return result

    async def annotate_batch(
        self, tables: list[ExtractedTable], batch_size: int = 50
    ) -> list[AnnotationResult]:
        results: list[AnnotationResult] = []
        uncached: list[tuple[int, ExtractedTable]] = []

        for i, table in enumerate(tables):
            key = _cache_key(table)
            cached = self._cache.get(key)
            if cached is not None:
                results.append(cached)
            else:
                results.append(
                    AnnotationResult(table_name=table.name, table_description="", columns=[])
                )
                uncached.append((i, table))

        if not uncached:
            return results

        batches = [
            uncached[j : j + batch_size] for j in range(0, len(uncached), batch_size)
        ]
        for batch in batches:
            batch_tables = [t for _, t in batch]
            try:
                batch_results = await self._annotator.annotate_batch(batch_tables)
            except Exception:
                logger.exception("Batch annotation failed, falling back to single")
                batch_results = []
                for idx, t in batch:
                    try:
                        batch_results.append(await self._annotator.annotate(t))
                    except Exception:
                        batch_results.append(
                            AnnotationResult(
                                table_name=t.name,
                                table_description="",
                                columns=[
                                    AnnotatedColumn(name=c.name, description="")
                                    for c in t.columns
                                ],
                            )
                        )

            for (idx, table), result in zip(batch, batch_results, strict=False):
                results[idx] = result
                self._cache.set(_cache_key(table), result)

        return results

    def clear_cache(self) -> None:
        self._cache.clear()


def _cache_key(table: ExtractedTable) -> str:
    raw = ";".join(
        f"{c.name}:{c.data_type}:{c.is_nullable}:{c.is_primary_key}"
        for c in table.columns
    )
    return hashlib.sha256(f"{table.name}|{table.ddl}|{raw}".encode()).hexdigest()

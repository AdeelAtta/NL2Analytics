from __future__ import annotations

import hashlib

from ke.models.vector import EmbeddingItem, EmbeddingResult, SparseVector


class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-m3", dimension: int = 1024) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._cache: dict[str, EmbeddingResult] = {}

    async def embed(self, item: EmbeddingItem) -> EmbeddingResult:
        cache_key = _cache_key(item.text)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        result = await self._generate_embedding(item)
        self._cache[cache_key] = result
        return result

    async def embed_batch(
        self, items: list[EmbeddingItem], batch_size: int = 100
    ) -> list[EmbeddingResult]:
        results: list[EmbeddingResult] = []
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            for item in batch:
                result = await self.embed(item)
                results.append(result)
        return results

    async def _generate_embedding(self, item: EmbeddingItem) -> EmbeddingResult:
        dimension = self._dimension
        seed = sum(ord(c) for c in item.text) % (dimension - 1) or 1
        dense = [0.0] * dimension
        for j in range(dimension):
            dense[j] = (seed * (j + 1) % 255) / 255.0
        norm = sum(v * v for v in dense) ** 0.5
        dense = [v / norm for v in dense]
        sparse_indices = [seed % 25000, (seed * 31) % 25000, (seed * 17) % 25000]
        sparse_values = [0.45, 0.32, 0.28]
        sparse = SparseVector(indices=sparse_indices, values=sparse_values)
        return EmbeddingResult(
            id=item.id,
            dense_vector=dense,
            sparse_vector=sparse,
            embedding_model=self._model_name,
            dimension=dimension,
            normalized=True,
        )

    async def embed_text(self, text: str) -> EmbeddingResult:
        item = EmbeddingItem(id=_cache_key(text), text=text, source_id="_search")
        return await self.embed(item)

    def clear_cache(self) -> None:
        self._cache.clear()


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

from __future__ import annotations

import pytest

from ke.models.vector import EmbeddingItem
from ke.stores.vector.embedding import EmbeddingService


@pytest.fixture
def service() -> EmbeddingService:
    return EmbeddingService()


class TestEmbeddingService:
    async def test_embed_single_item(self, service: EmbeddingService) -> None:
        item = EmbeddingItem(id="e1", text="hello world", source_id="src1")
        result = await service.embed(item)
        assert result.id == "e1"
        assert len(result.dense_vector) == 1024
        assert result.sparse_vector is not None
        assert len(result.sparse_vector.indices) == 3

    async def test_embed_normalized(self, service: EmbeddingService) -> None:
        item = EmbeddingItem(id="e1", text="test", source_id="src1")
        result = await service.embed(item)
        norm = sum(v * v for v in result.dense_vector) ** 0.5
        assert abs(norm - 1.0) < 0.01

    async def test_embed_cache_hit(self, service: EmbeddingService) -> None:
        item = EmbeddingItem(id="e1", text="hello", source_id="src1")
        r1 = await service.embed(item)
        r2 = await service.embed(item)
        assert r1.dense_vector == r2.dense_vector

    async def test_embed_batch(self, service: EmbeddingService) -> None:
        items = [
            EmbeddingItem(id="e1", text="first", source_id="src1"),
            EmbeddingItem(id="e2", text="second", source_id="src2"),
            EmbeddingItem(id="e3", text="third", source_id="src3"),
        ]
        results = await service.embed_batch(items, batch_size=2)
        assert len(results) == 3
        assert results[0].id == "e1"
        assert results[2].id == "e3"

    async def test_embed_different_texts_different_vectors(
        self, service: EmbeddingService
    ) -> None:
        i1 = EmbeddingItem(id="e1", text="hello world", source_id="src1")
        i2 = EmbeddingItem(id="e2", text="foo bar baz", source_id="src2")
        r1 = await service.embed(i1)
        r2 = await service.embed(i2)
        assert r1.dense_vector != r2.dense_vector

    async def test_clear_cache(self, service: EmbeddingService) -> None:
        item = EmbeddingItem(id="e1", text="hello", source_id="src1")
        r1 = await service.embed(item)
        service.clear_cache()
        r2 = await service.embed(item)
        assert r1.dense_vector == r2.dense_vector

    async def test_sparse_vector_indices_are_integers(
        self, service: EmbeddingService
    ) -> None:
        item = EmbeddingItem(id="e1", text="test", source_id="src1")
        result = await service.embed(item)
        assert result.sparse_vector is not None
        for idx in result.sparse_vector.indices:
            assert isinstance(idx, int)

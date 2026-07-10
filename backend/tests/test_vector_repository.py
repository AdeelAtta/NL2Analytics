from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ke.models.vector import (
    HybridSearchParams,
    SparseVector,
    VectorPayload,
    VectorPoint,
)
from ke.stores.vector.repository import (
    VectorRepository,
    _build_filter,
    _point_to_search_result,
    _tenant_collection_name,
)


class TestHelpers:
    def test_tenant_collection_name(self) -> None:
        assert _tenant_collection_name("tnt_1") == "tenant_tnt_1_embeddings"


class TestBuildFilter:
    def test_no_params_returns_empty_filter(self) -> None:
        params = HybridSearchParams(query="test")
        result = _build_filter(params)
        assert result.must is not None
        assert len(result.must) == 0

    def test_with_content_type(self) -> None:
        params = HybridSearchParams(query="test", content_type="schema_element")
        result = _build_filter(params)
        assert len(result.must) == 1

    def test_with_tenant_id(self) -> None:
        params = HybridSearchParams(query="test", tenant_id="tnt_1")
        result = _build_filter(params)
        assert len(result.must) == 1

    def test_with_both(self) -> None:
        params = HybridSearchParams(
            query="test", content_type="business_term", tenant_id="tnt_1"
        )
        result = _build_filter(params)
        assert len(result.must) == 2


class TestVectorRepository:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.get_collections = AsyncMock(
            return_value=MagicMock(collections=[])
        )
        client.create_collection = AsyncMock()
        client.upsert = AsyncMock(return_value=MagicMock(status=1))
        client.query_points = AsyncMock(
            return_value=MagicMock(points=[])
        )
        client.delete = AsyncMock()
        client.count = AsyncMock(return_value=MagicMock(count=0))
        client.get_collection = AsyncMock(
            return_value=MagicMock(
                status="green",
                indexed_vectors_count=100,
                points_count=50,
                segments_count=3,
            )
        )
        client.delete_collection = AsyncMock()
        return client

    @pytest.fixture
    def repo(self, mock_client: AsyncMock) -> VectorRepository:
        return VectorRepository(mock_client)

    async def test_ensure_collection_creates_new(
        self, repo: VectorRepository, mock_client: AsyncMock
    ) -> None:
        await repo.ensure_collection("tnt_1")
        mock_client.create_collection.assert_awaited_once()

    async def test_ensure_collection_skips_existing(self) -> None:
        client = AsyncMock()
        existing_col = MagicMock()
        existing_col.name = "tenant_tnt_1_embeddings"
        client.get_collections = AsyncMock(
            return_value=MagicMock(collections=[existing_col])
        )
        client.create_collection = AsyncMock()
        client.upsert = AsyncMock()
        client.query_points = AsyncMock()
        client.delete = AsyncMock()
        client.count = AsyncMock()
        client.get_collection = AsyncMock()
        client.delete_collection = AsyncMock()
        repo = VectorRepository(client)
        await repo.ensure_collection("tnt_1")
        client.create_collection.assert_not_called()

    async def test_upsert_points(
        self, repo: VectorRepository, mock_client: AsyncMock
    ) -> None:
        now = datetime.now(timezone.utc)
        points = [
            VectorPoint(
                id="pt1",
                dense_vector=[0.1] * 1024,
                payload=VectorPayload(
                    tenant_id="tnt_1",
                    content_type="schema_element",
                    source_id="src1",
                    text="test",
                    created_at=now,
                ),
            )
        ]
        result = await repo.upsert_points("tnt_1", points)
        assert result == 1
        mock_client.upsert.assert_awaited_once()

    async def test_search_returns_empty(
        self, repo: VectorRepository, mock_client: AsyncMock
    ) -> None:
        results = await repo.search("tnt_1", [0.1] * 1024)
        assert results == []

    async def test_search_hybrid_without_sparse_falls_back(
        self, repo: VectorRepository, mock_client: AsyncMock
    ) -> None:
        results = await repo.search_hybrid("tnt_1", [0.1] * 1024, None)
        assert results == []

    async def test_delete_points(
        self, repo: VectorRepository, mock_client: AsyncMock
    ) -> None:
        await repo.delete_points("tnt_1", ["pt1", "pt2"])
        mock_client.delete.assert_awaited_once()

    async def test_delete_by_filter(
        self, repo: VectorRepository, mock_client: AsyncMock
    ) -> None:
        await repo.delete_by_filter("tnt_1", content_type="schema_element")
        mock_client.delete.assert_awaited_once()

    async def test_count_points(
        self, repo: VectorRepository, mock_client: AsyncMock
    ) -> None:
        count = await repo.count_points("tnt_1")
        assert count == 0

    async def test_count_points_with_content_type(
        self, repo: VectorRepository, mock_client: AsyncMock
    ) -> None:
        count = await repo.count_points("tnt_1", content_type="schema_element")
        assert count == 0

    async def test_list_collections_all(
        self, repo: VectorRepository, mock_client: AsyncMock
    ) -> None:
        col1 = MagicMock()
        col1.name = "tenant_tnt_1_embeddings"
        col2 = MagicMock()
        col2.name = "tenant_tnt_2_embeddings"
        mock_client.get_collections = AsyncMock(
            return_value=MagicMock(collections=[col1, col2])
        )
        names = await repo.list_collections()
        assert len(names) == 2

    async def test_list_collections_filtered(self) -> None:
        client = AsyncMock()
        col1 = MagicMock()
        col1.name = "tenant_tnt_1_embeddings"
        col2 = MagicMock()
        col2.name = "tenant_tnt_2_embeddings"
        client.get_collections = AsyncMock(
            return_value=MagicMock(collections=[col1, col2])
        )
        client.delete = AsyncMock()
        client.count = AsyncMock()
        client.get_collection = AsyncMock()
        client.delete_collection = AsyncMock()
        repo = VectorRepository(client)
        names = await repo.list_collections(tenant_id="tnt_1")
        assert names == ["tenant_tnt_1_embeddings"]

    async def test_delete_collection(
        self, repo: VectorRepository, mock_client: AsyncMock
    ) -> None:
        await repo.delete_collection("tnt_1")
        mock_client.delete_collection.assert_awaited_once_with(
            collection_name="tenant_tnt_1_embeddings"
        )

    async def test_collection_info(
        self, repo: VectorRepository, mock_client: AsyncMock
    ) -> None:
        info = await repo.collection_info("tnt_1")
        assert info["name"] == "tenant_tnt_1_embeddings"
        assert info["status"] == "green"
        assert info["vectors_count"] == 100
        assert info["points_count"] == 50
        assert info["segments_count"] == 3

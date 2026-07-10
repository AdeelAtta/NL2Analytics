from __future__ import annotations

from datetime import UTC, datetime

from ke.models.vector import (
    EmbeddingItem,
    EmbeddingResult,
    HybridSearchParams,
    SearchResult,
    SparseVector,
    VectorPayload,
    VectorPoint,
)


def test_sparse_vector_valid() -> None:
    sv = SparseVector(indices=[1, 2, 3], values=[0.1, 0.2, 0.3])
    assert sv.indices == [1, 2, 3]
    assert sv.values == [0.1, 0.2, 0.3]


def test_embedding_item_defaults() -> None:
    item = EmbeddingItem(id="e1", text="hello world", source_id="src1")
    assert item.content_type == "schema_element"


def test_embedding_result_defaults() -> None:
    result = EmbeddingResult(id="e1", dense_vector=[0.1, 0.2])
    assert result.embedding_model == "BAAI/bge-m3"
    assert result.dimension == 1024
    assert result.normalized is True


def test_vector_payload_requires_tenant_id() -> None:
    now = datetime.now(UTC)
    payload = VectorPayload(
        tenant_id="tnt_1",
        content_type="schema_element",
        source_id="src1",
        text="some text",
        created_at=now,
    )
    assert payload.tenant_id == "tnt_1"
    assert payload.metadata == {}


def test_vector_point_round_trip() -> None:
    now = datetime.now(UTC)
    payload = VectorPayload(
        tenant_id="tnt_1",
        content_type="query_pattern",
        source_id="qry1",
        text="SELECT * FROM users",
        created_at=now,
    )
    point = VectorPoint(
        id="pt1",
        dense_vector=[0.1] * 1024,
        sparse_vector=SparseVector(indices=[1, 2], values=[0.5, 0.3]),
        payload=payload,
    )
    assert point.id == "pt1"
    assert len(point.dense_vector) == 1024
    assert point.payload.content_type == "query_pattern"
    assert point.sparse_vector is not None


def test_search_result_defaults() -> None:
    now = datetime.now(UTC)
    payload = VectorPayload(
        tenant_id="tnt_1",
        content_type="schema_element",
        source_id="src1",
        text="some text",
        created_at=now,
    )
    result = SearchResult(id="r1", score=0.95, payload=payload)
    assert result.score == 0.95
    assert result.dense_score is None
    assert result.sparse_score is None


def test_hybrid_search_params_defaults() -> None:
    params = HybridSearchParams(query="test query")
    assert params.limit == 20
    assert params.dense_weight == 0.7
    assert params.tenant_id is None


def test_hybrid_search_params_custom() -> None:
    params = HybridSearchParams(
        query="test",
        content_type="business_term",
        limit=10,
        dense_weight=0.5,
        tenant_id="tnt_1",
    )
    assert params.content_type == "business_term"
    assert params.limit == 10
    assert params.dense_weight == 0.5
    assert params.tenant_id == "tnt_1"

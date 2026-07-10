from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from schema_intelligence.annotators.base import (
    AnnotatedColumn,
    AnnotationResult,
    BaseAnnotator,
)
from schema_intelligence.annotators.llm_provider import LLMAnnotator
from schema_intelligence.annotators.rule_based import RuleBasedAnnotator
from schema_intelligence.connectors.base import (
    ExtractedColumn,
    ExtractedTable,
    ForeignKeyRef,
)
from schema_intelligence.services.annotation import (
    AnnotationService,
    DictCache,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def users_table() -> ExtractedTable:
    return ExtractedTable(
        name="users",
        columns=[
            ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True),
            ExtractedColumn(name="email", ordinal_position=2, data_type="VARCHAR(255)", is_nullable=False),
            ExtractedColumn(name="first_name", ordinal_position=3, data_type="VARCHAR(100)", is_nullable=True),
            ExtractedColumn(name="last_name", ordinal_position=4, data_type="VARCHAR(100)", is_nullable=True),
            ExtractedColumn(name="is_active", ordinal_position=5, data_type="BOOLEAN", is_nullable=False, default_value="true"),
            ExtractedColumn(name="created_at", ordinal_position=6, data_type="TIMESTAMPTZ", is_nullable=False, default_value="NOW()"),
        ],
        ddl="CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) NOT NULL, ...)",
    )


@pytest.fixture
def orders_table() -> ExtractedTable:
    return ExtractedTable(
        name="orders",
        columns=[
            ExtractedColumn(name="id", ordinal_position=1, data_type="BIGSERIAL", is_nullable=False, is_primary_key=True),
            ExtractedColumn(name="user_id", ordinal_position=2, data_type="INT", is_nullable=False, foreign_key=ForeignKeyRef(ref_table="users", ref_column="id")),
            ExtractedColumn(name="total", ordinal_position=3, data_type="DECIMAL(12,2)", is_nullable=False),
            ExtractedColumn(name="status", ordinal_position=4, data_type="VARCHAR(20)", is_nullable=False, default_value="pending"),
            ExtractedColumn(name="created_at", ordinal_position=5, data_type="TIMESTAMPTZ", is_nullable=False, default_value="NOW()"),
        ],
        row_count_estimate=10000,
    )


@pytest.fixture
def junction_table() -> ExtractedTable:
    return ExtractedTable(
        name="user_role_mapping",
        columns=[
            ExtractedColumn(name="user_id", ordinal_position=1, data_type="INT", is_nullable=False, is_primary_key=True, foreign_key=ForeignKeyRef(ref_table="users", ref_column="id")),
            ExtractedColumn(name="role_id", ordinal_position=2, data_type="INT", is_nullable=False, is_primary_key=True, foreign_key=ForeignKeyRef(ref_table="roles", ref_column="id")),
            ExtractedColumn(name="created_at", ordinal_position=3, data_type="TIMESTAMP", is_nullable=False, default_value="NOW()"),
        ],
    )


@pytest.fixture
def config_table() -> ExtractedTable:
    return ExtractedTable(
        name="app_settings",
        columns=[
            ExtractedColumn(name="key", ordinal_position=1, data_type="VARCHAR(100)", is_nullable=False, is_primary_key=True),
            ExtractedColumn(name="value", ordinal_position=2, data_type="JSONB", is_nullable=True),
            ExtractedColumn(name="description", ordinal_position=3, data_type="TEXT", is_nullable=True),
        ],
    )


# ---------------------------------------------------------------------------
# Test AnnotationResult / AnnotatedColumn
# ---------------------------------------------------------------------------

class TestAnnotationModels:
    def test_annotated_column_minimal(self) -> None:
        col = AnnotatedColumn(name="id", description="Identifier")
        assert col.name == "id"
        assert col.description == "Identifier"

    def test_annotation_result_defaults(self) -> None:
        r = AnnotationResult(table_name="t", table_description="desc")
        assert r.columns == []

    def test_annotation_result_with_columns(self) -> None:
        cols = [AnnotatedColumn(name="a", description="col a")]
        r = AnnotationResult(table_name="t", table_description="desc", columns=cols)
        assert len(r.columns) == 1


# ---------------------------------------------------------------------------
# Test BaseAnnotator ABC
# ---------------------------------------------------------------------------

class TestBaseAnnotator:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            BaseAnnotator()  # type: ignore[abstract]

    def test_concrete_subclass(self) -> None:
        class Concrete(BaseAnnotator):
            async def annotate(self, table: ExtractedTable) -> AnnotationResult:
                return AnnotationResult(table_name=table.name, table_description="")

            async def annotate_batch(self, tables: list[ExtractedTable]) -> list[AnnotationResult]:
                return [await self.annotate(t) for t in tables]

        c = Concrete()
        assert isinstance(c, BaseAnnotator)


# ---------------------------------------------------------------------------
# Test RuleBasedAnnotator
# ---------------------------------------------------------------------------

class TestRuleBasedAnnotator:
    @pytest.mark.asyncio
    async def test_annotate_returns_result(self, users_table: ExtractedTable) -> None:
        ann = RuleBasedAnnotator()
        result = await ann.annotate(users_table)
        assert result.table_name == "users"
        assert result.table_description
        assert len(result.columns) == len(users_table.columns)

    @pytest.mark.asyncio
    async def test_id_column_description(self, users_table: ExtractedTable) -> None:
        ann = RuleBasedAnnotator()
        result = await ann.annotate(users_table)
        id_col = next(c for c in result.columns if c.name == "id")
        assert "Unique identifier" in id_col.description
        assert "Primary key" in id_col.description

    @pytest.mark.asyncio
    async def test_email_column_description(self, users_table: ExtractedTable) -> None:
        ann = RuleBasedAnnotator()
        result = await ann.annotate(users_table)
        email_col = next(c for c in result.columns if c.name == "email")
        assert "Email" in email_col.description

    @pytest.mark.asyncio
    async def test_foreign_key_column(self, orders_table: ExtractedTable) -> None:
        ann = RuleBasedAnnotator()
        result = await ann.annotate(orders_table)
        uid_col = next(c for c in result.columns if c.name == "user_id")
        assert "Foreign key" in uid_col.description
        assert "users" in uid_col.description
        assert "id" in uid_col.description

    @pytest.mark.asyncio
    async def test_not_null_column_annotation(self, users_table: ExtractedTable) -> None:
        ann = RuleBasedAnnotator()
        result = await ann.annotate(users_table)
        email_col = next(c for c in result.columns if c.name == "email")
        assert "Required" in email_col.description or "Cannot be null" in email_col.description

    @pytest.mark.asyncio
    async def test_default_value_annotation(self, orders_table: ExtractedTable) -> None:
        ann = RuleBasedAnnotator()
        result = await ann.annotate(orders_table)
        status_col = next(c for c in result.columns if c.name == "status")
        assert "Defaults to" in status_col.description

    @pytest.mark.asyncio
    async def test_junction_table_description(self, junction_table: ExtractedTable) -> None:
        ann = RuleBasedAnnotator()
        result = await ann.annotate(junction_table)
        assert "mapping" in result.table_description.lower() or "many to many" in result.table_description.lower() or "relationship" in result.table_description.lower()

    @pytest.mark.asyncio
    async def test_config_table_description(self, config_table: ExtractedTable) -> None:
        ann = RuleBasedAnnotator()
        result = await ann.annotate(config_table)
        assert "configuration" in result.table_description.lower() or "Stores information" in result.table_description

    @pytest.mark.asyncio
    async def test_created_at_column(self, users_table: ExtractedTable) -> None:
        ann = RuleBasedAnnotator()
        result = await ann.annotate(users_table)
        ca_col = next(c for c in result.columns if c.name == "created_at")
        assert "Timestamp" in ca_col.description

    @pytest.mark.asyncio
    async def test_is_active_column(self, users_table: ExtractedTable) -> None:
        ann = RuleBasedAnnotator()
        result = await ann.annotate(users_table)
        is_col = next(c for c in result.columns if c.name == "is_active")
        assert "active" in is_col.description.lower()

    @pytest.mark.asyncio
    async def test_batch_annotation(self, users_table: ExtractedTable, orders_table: ExtractedTable) -> None:
        ann = RuleBasedAnnotator()
        results = await ann.annotate_batch([users_table, orders_table])
        assert len(results) == 2
        assert results[0].table_name == "users"
        assert results[1].table_name == "orders"

    @pytest.mark.asyncio
    async def test_comment_is_used(self) -> None:
        table = ExtractedTable(
            name="test",
            columns=[ExtractedColumn(name="a", ordinal_position=1, data_type="INT", is_nullable=True)],
            comment="Custom comment",
        )
        ann = RuleBasedAnnotator()
        result = await ann.annotate(table)
        assert result.table_description == "Custom comment"

    @pytest.mark.asyncio
    async def test_column_comment_is_used(self) -> None:
        table = ExtractedTable(
            name="test",
            columns=[
                ExtractedColumn(
                    name="a", ordinal_position=1, data_type="INT", is_nullable=True, comment="My column"
                )
            ],
        )
        ann = RuleBasedAnnotator()
        result = await ann.annotate(table)
        assert result.columns[0].description == "My column"

    @pytest.mark.asyncio
    async def test_name_pattern_for_camel_case(self) -> None:
        table = ExtractedTable(
            name="orderItems",
            columns=[ExtractedColumn(name="itemName", ordinal_position=1, data_type="VARCHAR(100)", is_nullable=True)],
        )
        ann = RuleBasedAnnotator()
        result = await ann.annotate(table)
        assert result.columns[0].description

    @pytest.mark.asyncio
    async def test_dtype_hint_included(self) -> None:
        table = ExtractedTable(
            name="test",
            columns=[
                ExtractedColumn(
                    name="amount",
                    ordinal_position=1,
                    data_type="DECIMAL(10,2)",
                    is_nullable=True,
                    numeric_precision=10,
                    numeric_scale=2,
                )
            ],
        )
        ann = RuleBasedAnnotator()
        result = await ann.annotate(table)
        assert "precision" in result.columns[0].description.lower() or "scale" in result.columns[0].description.lower()


# ---------------------------------------------------------------------------
# Test LLMAnnotator
# ---------------------------------------------------------------------------

class TestLLMAnnotator:
    def test_init_defaults(self) -> None:
        ann = LLMAnnotator()
        assert ann._endpoint == "http://localhost:8000/v1"
        assert ann._model == "qwen2.5-72b"

    def test_custom_config(self) -> None:
        ann = LLMAnnotator(
            endpoint="http://llm.internal:8080/v1",
            model="gpt-4",
            api_key="sk-test",
            timeout_seconds=120,
            max_retries=3,
        )
        assert ann._endpoint == "http://llm.internal:8080/v1"
        assert ann._max_retries == 3

    @pytest.mark.asyncio
    async def test_parse_response(self) -> None:
        ann = LLMAnnotator()
        response = {
            "table_description": "Stores user accounts.",
            "columns": [
                {"name": "id", "description": "Unique identifier."},
            ],
        }
        result = ann._parse_response("users", response)
        assert result.table_description == "Stores user accounts."
        assert result.columns[0].description == "Unique identifier."

    @pytest.mark.asyncio
    async def test_call_llm_success(self) -> None:
        ann = LLMAnnotator()
        mock_response = {
            "table_description": "Test table.",
            "columns": [{"name": "a", "description": "Column a."}],
        }
        response_body = {
            "choices": [{"message": {"content": json.dumps(mock_response)}}]
        }

        class FakeResponse:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return response_body

        class FakeClient:
            async def __aenter__(self) -> FakeClient:
                return self

            async def __aexit__(self, *args: object) -> None:
                pass

            async def post(self, *args: object, **kwargs: object) -> FakeResponse:
                return FakeResponse()

        with patch("httpx.AsyncClient", return_value=FakeClient()):
            result = await ann.annotate(
                ExtractedTable(
                    name="test",
                    columns=[ExtractedColumn(name="a", ordinal_position=1, data_type="INT", is_nullable=True)],
                )
            )
            assert result.table_name == "test"
            assert result.table_description == "Test table."

    @pytest.mark.asyncio
    async def test_call_llm_retries_then_raises(self) -> None:
        ann = LLMAnnotator(max_retries=1)

        class FailingClient:
            async def __aenter__(self) -> FailingClient:
                return self

            async def __aexit__(self, *args: object) -> None:
                pass

            async def post(self, *args: object, **kwargs: object) -> object:
                raise ConnectionError("LLM unavailable")

        with patch("httpx.AsyncClient", return_value=FailingClient()):
            with pytest.raises(RuntimeError, match="LLM annotator failed"):
                await ann.annotate(
                    ExtractedTable(
                        name="test",
                        columns=[ExtractedColumn(name="a", ordinal_position=1, data_type="INT", is_nullable=True)],
                    )
                )

    @pytest.mark.asyncio
    async def test_build_prompt_includes_schema(self) -> None:
        ann = LLMAnnotator()
        table = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="email", ordinal_position=2, data_type="VARCHAR(255)", is_nullable=False),
            ],
        )
        prompt = ann._build_prompt(table)
        assert "users" in prompt
        assert "id" in prompt
        assert "SERIAL" in prompt
        assert "[PK]" in prompt
        assert "[NOT NULL]" in prompt


# ---------------------------------------------------------------------------
# Test AnnotationService
# ---------------------------------------------------------------------------

class TestAnnotationService:
    @pytest.mark.asyncio
    async def test_annotate_with_default_annotator(self, users_table: ExtractedTable) -> None:
        service = AnnotationService()
        result = await service.annotate(users_table)
        assert result.table_name == "users"
        assert result.table_description

    @pytest.mark.asyncio
    async def test_cache_hit(self, users_table: ExtractedTable) -> None:
        service = AnnotationService()
        r1 = await service.annotate(users_table)
        r2 = await service.annotate(users_table)
        assert r1 is r2  # Same cached object

    @pytest.mark.asyncio
    async def test_cache_key_differentiates_tables(self) -> None:
        t1 = ExtractedTable(
            name="t",
            columns=[ExtractedColumn(name="a", ordinal_position=1, data_type="INT", is_nullable=True)],
        )
        t2 = ExtractedTable(
            name="t",
            columns=[ExtractedColumn(name="b", ordinal_position=1, data_type="INT", is_nullable=True)],
        )
        service = AnnotationService()
        r1 = await service.annotate(t1)
        r2 = await service.annotate(t2)
        assert r1 is not r2

    @pytest.mark.asyncio
    async def test_annotate_batch(self, users_table: ExtractedTable, orders_table: ExtractedTable) -> None:
        service = AnnotationService()
        results = await service.annotate_batch([users_table, orders_table])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_annotate_batch_all_cached(self, users_table: ExtractedTable) -> None:
        service = AnnotationService()
        await service.annotate(users_table)
        with patch.object(service._annotator, "annotate_batch", wraps=service._annotator.annotate_batch) as spy:
            results = await service.annotate_batch([users_table])
            spy.assert_not_called()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_clear_cache(self, users_table: ExtractedTable) -> None:
        service = AnnotationService()
        r1 = await service.annotate(users_table)
        service.clear_cache()
        r2 = await service.annotate(users_table)
        assert r1 is not r2

    def test_dict_cache(self) -> None:
        cache = DictCache()
        assert cache.get("x") is None
        result = AnnotationResult(table_name="t", table_description="d")
        cache.set("x", result)
        assert cache.get("x") is result
        cache.clear()
        assert cache.get("x") is None

    @pytest.mark.asyncio
    async def test_custom_cache_backend(self, users_table: ExtractedTable) -> None:
        cache = DictCache()
        service = AnnotationService(cache=cache)
        result = await service.annotate(users_table)
        assert cache.get(_cache_key_for_test(users_table)) is result

    @pytest.mark.asyncio
    async def test_custom_annotator(self, users_table: ExtractedTable) -> None:
        class FixedAnnotator(BaseAnnotator):
            async def annotate(self, table: ExtractedTable) -> AnnotationResult:
                return AnnotationResult(table_name=table.name, table_description="fixed")

            async def annotate_batch(self, tables: list[ExtractedTable]) -> list[AnnotationResult]:
                return [await self.annotate(t) for t in tables]

        service = AnnotationService(annotator=FixedAnnotator())
        result = await service.annotate(users_table)
        assert result.table_description == "fixed"

    @pytest.mark.asyncio
    async def test_batch_fallback_on_error(self, users_table: ExtractedTable) -> None:
        class FailingAnnotator(BaseAnnotator):
            async def annotate(self, table: ExtractedTable) -> AnnotationResult:
                return AnnotationResult(table_name=table.name, table_description="fallback")

            async def annotate_batch(self, tables: list[ExtractedTable]) -> list[AnnotationResult]:
                raise RuntimeError("batch failed")

        service = AnnotationService(annotator=FailingAnnotator())
        results = await service.annotate_batch([users_table])
        assert results[0].table_description == "fallback"


def _cache_key_for_test(table: ExtractedTable) -> str:
    from schema_intelligence.services.annotation import _cache_key
    return _cache_key(table)

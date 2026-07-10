from __future__ import annotations

import pytest

from schema_intelligence.connectors.base import (
    ExtractedColumn,
    ExtractedTable,
    ForeignKeyRef,
)
from schema_intelligence.inference.base import (
    BaseInferenceEngine,
    InferenceContext,
    InferredRelationship,
)
from schema_intelligence.inference.engine import RelationshipInferenceService
from schema_intelligence.inference.name_based import (
    NameBasedInferenceEngine,
    _is_compatible_type,
    _is_integer_type,
    _singularize,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def orders_customers_schema() -> list[ExtractedTable]:
    return [
        ExtractedTable(
            name="customers",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="name", ordinal_position=2, data_type="VARCHAR(100)", is_nullable=True),
                ExtractedColumn(name="email", ordinal_position=3, data_type="VARCHAR(255)", is_nullable=False),
            ],
        ),
        ExtractedTable(
            name="orders",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="BIGSERIAL", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="customer_id", ordinal_position=2, data_type="INT", is_nullable=False),
                ExtractedColumn(name="total", ordinal_position=3, data_type="DECIMAL(12,2)", is_nullable=False),
                ExtractedColumn(name="created_at", ordinal_position=4, data_type="TIMESTAMPTZ", is_nullable=False),
            ],
        ),
    ]


@pytest.fixture
def junction_schema() -> list[ExtractedTable]:
    return [
        ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="name", ordinal_position=2, data_type="VARCHAR(100)", is_nullable=True),
            ],
        ),
        ExtractedTable(
            name="roles",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="name", ordinal_position=2, data_type="VARCHAR(50)", is_nullable=False),
            ],
        ),
        ExtractedTable(
            name="user_role_mapping",
            columns=[
                ExtractedColumn(name="user_id", ordinal_position=1, data_type="INT", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="role_id", ordinal_position=2, data_type="INT", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="created_at", ordinal_position=3, data_type="TIMESTAMP", is_nullable=False),
            ],
        ),
    ]


@pytest.fixture
def self_ref_schema() -> list[ExtractedTable]:
    return [
        ExtractedTable(
            name="employees",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="name", ordinal_position=2, data_type="VARCHAR(100)", is_nullable=True),
                ExtractedColumn(name="manager_id", ordinal_position=3, data_type="INT", is_nullable=True),
            ],
        ),
    ]


@pytest.fixture
def already_fk_schema() -> list[ExtractedTable]:
    return [
        ExtractedTable(
            name="customers",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True),
            ],
        ),
        ExtractedTable(
            name="orders",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="BIGSERIAL", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="customer_id", ordinal_position=2, data_type="INT", is_nullable=False, foreign_key=ForeignKeyRef(ref_table="customers", ref_column="id")),
            ],
        ),
    ]


@pytest.fixture
def empty_schema() -> list[ExtractedTable]:
    return [
        ExtractedTable(
            name="empty",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_singularize_ies(self) -> None:
        assert _singularize("categories") == "category"

    def test_singularize_ses(self) -> None:
        assert _singularize("processes") == "process"

    def test_singularize_regular(self) -> None:
        assert _singularize("customers") == "customer"

    def test_singularize_no_s(self) -> None:
        assert _singularize("customer") == "customer"

    def test_singularize_ss(self) -> None:
        assert _singularize("address") == "address"

    def test_singularize_xes(self) -> None:
        assert _singularize("boxes") == "box"

    def test_is_integer_type_int(self) -> None:
        assert _is_integer_type("INT") is True

    def test_is_integer_type_serial(self) -> None:
        assert _is_integer_type("SERIAL") is True

    def test_is_integer_type_varchar(self) -> None:
        assert _is_integer_type("VARCHAR(255)") is False

    def test_is_compatible_type_same(self) -> None:
        assert _is_compatible_type("INT", "INT") is True

    def test_is_compatible_type_int_family(self) -> None:
        assert _is_compatible_type("INT", "BIGINT") is True

    def test_is_compatible_type_varchar_family(self) -> None:
        assert _is_compatible_type("VARCHAR(255)", "TEXT") is True

    def test_is_compatible_type_incompatible(self) -> None:
        assert _is_compatible_type("INT", "VARCHAR") is False


# ---------------------------------------------------------------------------
# Test InferredRelationship / InferenceContext
# ---------------------------------------------------------------------------

class TestModels:
    def test_inferred_relationship_defaults(self) -> None:
        r = InferredRelationship(
            source_table="a", source_column="x", target_table="b", target_column="y"
        )
        assert r.confidence == 1.0
        assert r.strategy == "unknown"
        assert r.relationship_type == "inferred"

    def test_inference_context_defaults(self) -> None:
        ctx = InferenceContext(tables=[])
        assert ctx.naming_confidence == 0.7
        assert ctx.min_confidence == 0.3

    def test_base_engine_abc(self) -> None:
        with pytest.raises(TypeError):
            BaseInferenceEngine()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Test NameBasedInferenceEngine
# ---------------------------------------------------------------------------

class TestNameBasedInferenceEngine:
    def test_naming_heuristic(
        self, orders_customers_schema: list[ExtractedTable]
    ) -> None:
        engine = NameBasedInferenceEngine()
        context = InferenceContext(tables=orders_customers_schema)
        results = engine.infer(context)
        rels = {(r.source_table, r.source_column, r.target_table): r for r in results}
        assert ("orders", "customer_id", "customers") in rels
        assert "naming_heuristic" in rels[("orders", "customer_id", "customers")].strategy

    def test_reverse_naming(self) -> None:
        tables = [
            ExtractedTable(
                name="customers",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True)],
            ),
            ExtractedTable(
                name="orders",
                columns=[ExtractedColumn(name="customers_id", ordinal_position=1, data_type="INT", is_nullable=True)],
            ),
        ]
        engine = NameBasedInferenceEngine()
        context = InferenceContext(tables=tables)
        results = engine.infer(context)
        rels = {(r.source_table, r.source_column, r.target_table) for r in results}
        assert ("orders", "customers_id", "customers") in rels

    def test_self_reference(self, self_ref_schema: list[ExtractedTable]) -> None:
        engine = NameBasedInferenceEngine()
        context = InferenceContext(tables=self_ref_schema)
        results = engine.infer(context)
        rels = {(r.source_table, r.source_column, r.target_table): r for r in results}
        assert ("employees", "manager_id", "employees") in rels
        assert rels[("employees", "manager_id", "employees")].strategy == "self_reference"

    def test_junction_table(
        self, junction_schema: list[ExtractedTable]
    ) -> None:
        engine = NameBasedInferenceEngine()
        context = InferenceContext(tables=junction_schema)
        results = engine.infer(context)
        rels = {(r.source_table, r.source_column, r.target_table): r for r in results}
        assert ("user_role_mapping", "user_id", "users") in rels
        assert ("user_role_mapping", "role_id", "roles") in rels
        rel_types = {r.relationship_type for r in results if r.source_table == "user_role_mapping"}
        assert "junction" in rel_types

    def test_existing_fk_excluded(
        self, already_fk_schema: list[ExtractedTable]
    ) -> None:
        engine = NameBasedInferenceEngine()
        context = InferenceContext(tables=already_fk_schema)
        results = engine.infer(context)
        for r in results:
            assert not (
                r.source_table == "orders"
                and r.source_column == "customer_id"
                and r.target_table == "customers"
            )

    def test_empty_schema(self, empty_schema: list[ExtractedTable]) -> None:
        engine = NameBasedInferenceEngine()
        context = InferenceContext(tables=empty_schema)
        results = engine.infer(context)
        assert results == []

    def test_score_fusion(self) -> None:
        tables = [
            ExtractedTable(
                name="products",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True)],
            ),
            ExtractedTable(
                name="orders",
                columns=[
                    ExtractedColumn(name="id", ordinal_position=1, data_type="BIGSERIAL", is_nullable=False, is_primary_key=True),
                    ExtractedColumn(name="products_id", ordinal_position=2, data_type="INT", is_nullable=True),
                ],
            ),
            ExtractedTable(
                name="inventory",
                columns=[ExtractedColumn(name="product_id", ordinal_position=1, data_type="INT", is_nullable=True)],
            ),
        ]
        engine = NameBasedInferenceEngine()
        context = InferenceContext(tables=tables)
        results = engine.infer(context)
        # orders.products_id -> products.id should be inferred by both naming and reverse naming
        for r in results:
            if (r.source_table, r.source_column, r.target_table) == ("orders", "products_id", "products"):
                assert "+" in r.strategy
                assert r.confidence > 0.7

    def test_min_confidence_filter(self) -> None:
        tables = [
            ExtractedTable(
                name="a",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False, is_primary_key=True)],
            ),
            ExtractedTable(
                name="b",
                columns=[ExtractedColumn(name="a_col", ordinal_position=1, data_type="INT", is_nullable=True)],
            ),
        ]
        engine = NameBasedInferenceEngine()
        context = InferenceContext(tables=tables, min_confidence=0.5)
        results = engine.infer(context)
        for r in results:
            assert r.confidence >= 0.5

    def test_no_false_positives(self) -> None:
        tables = [
            ExtractedTable(
                name="products",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True)],
            ),
            ExtractedTable(
                name="users",
                columns=[
                    ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True),
                    ExtractedColumn(name="name", ordinal_position=2, data_type="VARCHAR(100)", is_nullable=True),
                ],
            ),
        ]
        engine = NameBasedInferenceEngine()
        context = InferenceContext(tables=tables)
        results = engine.infer(context)
        assert len(results) == 0  # No *_id columns to match

    def test_plural_table_name(self) -> None:
        tables = [
            ExtractedTable(
                name="users",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True)],
            ),
            ExtractedTable(
                name="orders",
                columns=[ExtractedColumn(name="user_id", ordinal_position=1, data_type="INT", is_nullable=True)],
            ),
        ]
        engine = NameBasedInferenceEngine()
        context = InferenceContext(tables=tables)
        results = engine.infer(context)
        rels = {(r.source_table, r.source_column, r.target_table) for r in results}
        assert ("orders", "user_id", "users") in rels


# ---------------------------------------------------------------------------
# Test RelationshipInferenceService
# ---------------------------------------------------------------------------

class TestRelationshipInferenceService:
    def test_infer_basic(
        self, orders_customers_schema: list[ExtractedTable]
    ) -> None:
        service = RelationshipInferenceService()
        results = service.infer(orders_customers_schema)
        assert len(results) >= 1

    def test_infer_junction(
        self, junction_schema: list[ExtractedTable]
    ) -> None:
        service = RelationshipInferenceService()
        results = service.infer(junction_schema)
        assert len(results) >= 2

    def test_custom_threshold(
        self, orders_customers_schema: list[ExtractedTable]
    ) -> None:
        service = RelationshipInferenceService(min_confidence=0.8)
        results = service.infer(orders_customers_schema)
        for r in results:
            assert r.confidence >= 0.8

    def test_custom_confidence_scores(self) -> None:
        tables = [
            ExtractedTable(
                name="a",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="SERIAL", is_nullable=False, is_primary_key=True)],
            ),
            ExtractedTable(
                name="b",
                columns=[ExtractedColumn(name="a_id", ordinal_position=1, data_type="INT", is_nullable=True)],
            ),
        ]
        service = RelationshipInferenceService(naming_confidence=0.5)
        results = service.infer(tables)
        a_id_rel = [r for r in results if r.source_column == "a_id"]
        assert len(a_id_rel) == 1
        assert "naming_heuristic" in a_id_rel[0].strategy
        assert a_id_rel[0].confidence == 0.7  # fused: naming(0.5) + reverse_naming(0.5) + fusion_bonus(0.2)

    def test_empty_input(self) -> None:
        service = RelationshipInferenceService()
        results = service.infer([])
        assert results == []

    def test_no_duplicates(self, junction_schema: list[ExtractedTable]) -> None:
        service = RelationshipInferenceService()
        results = service.infer(junction_schema)
        keys = {(r.source_table, r.source_column, r.target_table, r.target_column) for r in results}
        assert len(keys) == len(results)

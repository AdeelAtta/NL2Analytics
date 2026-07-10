from __future__ import annotations

from datetime import UTC, datetime

import pytest

from schema_intelligence.annotators.base import AnnotatedColumn, AnnotationResult
from schema_intelligence.connectors.base import (
    ExtractedColumn,
    ExtractedSchemaInfo,
    ExtractedTable,
)
from schema_intelligence.inference.base import InferredRelationship
from schema_intelligence.sync.models import (
    SyncChange,
    SyncChangeType,
    SyncResult,
    SyncState,
    table_signature,
)
from schema_intelligence.sync.orchestrator import (
    SyncOrchestrator,
    _compute_signatures,
    _detect_changes,
    _filter_schemas,
)


# ---------------------------------------------------------------------------
# table_signature
# ---------------------------------------------------------------------------

class TestTableSignature:
    def test_signature_based_on_ddl(self) -> None:
        t1 = ExtractedTable(name="users", columns=[], ddl="CREATE TABLE users (id INT)")
        t2 = ExtractedTable(name="users", columns=[], ddl="CREATE TABLE users (id INT)")
        assert table_signature(t1) == table_signature(t2)

    def test_signature_differs_for_different_ddl(self) -> None:
        t1 = ExtractedTable(name="users", columns=[], ddl="CREATE TABLE users (id INT)")
        t2 = ExtractedTable(name="users", columns=[], ddl="CREATE TABLE users (name TEXT)")
        assert table_signature(t1) != table_signature(t2)

    def test_signature_based_on_columns(self) -> None:
        t1 = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="name", ordinal_position=2, data_type="VARCHAR", is_nullable=True),
            ],
        )
        t2 = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False, is_primary_key=True),
                ExtractedColumn(name="name", ordinal_position=2, data_type="VARCHAR", is_nullable=True),
            ],
        )
        assert table_signature(t1) == table_signature(t2)

    def test_signature_differs_for_different_columns(self) -> None:
        t1 = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False),
            ],
        )
        t2 = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="name", ordinal_position=1, data_type="VARCHAR", is_nullable=True),
            ],
        )
        assert table_signature(t1) != table_signature(t2)

    def test_signature_differs_for_different_types(self) -> None:
        t1 = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False),
            ],
        )
        t2 = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="BIGINT", is_nullable=False),
            ],
        )
        assert table_signature(t1) != table_signature(t2)

    def test_signature_stable_ordering(self) -> None:
        cols_a = [
            ExtractedColumn(name="a", ordinal_position=1, data_type="INT", is_nullable=False),
            ExtractedColumn(name="b", ordinal_position=2, data_type="TEXT", is_nullable=True),
        ]
        cols_b = [
            ExtractedColumn(name="a", ordinal_position=1, data_type="INT", is_nullable=False),
            ExtractedColumn(name="b", ordinal_position=2, data_type="TEXT", is_nullable=True),
        ]
        t1 = ExtractedTable(name="t", columns=cols_a)
        t2 = ExtractedTable(name="t", columns=cols_b)
        assert table_signature(t1) == table_signature(t2)

    def test_signature_ddl_takes_precedence(self) -> None:
        t = ExtractedTable(
            name="users",
            ddl="CREATE TABLE users (id INT)",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="BIGINT", is_nullable=False),
            ],
        )
        col_only = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="BIGINT", is_nullable=False),
            ],
        )
        assert table_signature(t) != table_signature(col_only)

    def test_signature_empty_table(self) -> None:
        t = ExtractedTable(name="empty", columns=[])
        sig = table_signature(t)
        assert isinstance(sig, str)
        assert len(sig) == 64


# ---------------------------------------------------------------------------
# _compute_signatures
# ---------------------------------------------------------------------------

class TestComputeSignatures:
    def test_returns_dict_keyed_by_name(self) -> None:
        tables = [
            ExtractedTable(name="a", columns=[]),
            ExtractedTable(name="b", columns=[]),
        ]
        sigs = _compute_signatures(tables)
        assert set(sigs.keys()) == {"a", "b"}
        assert all(len(v) == 64 for v in sigs.values())


# ---------------------------------------------------------------------------
# _detect_changes
# ---------------------------------------------------------------------------

class TestDetectChanges:
    def test_all_added_when_previous_empty(self) -> None:
        tables = [
            ExtractedTable(name="a", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
            ExtractedTable(name="b", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
        ]
        changes = _detect_changes(previous_signatures={}, current_tables=tables)
        added = [c for c in changes if c.change_type == SyncChangeType.ADDED]
        assert len(added) == 2

    def test_all_unchanged(self) -> None:
        tables = [
            ExtractedTable(name="a", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
        ]
        sigs = _compute_signatures(tables)
        changes = _detect_changes(previous_signatures=sigs, current_tables=tables)
        unchanged = [c for c in changes if c.change_type == SyncChangeType.UNCHANGED]
        assert len(unchanged) == 1
        assert unchanged[0].table.name == "a"

    def test_changed_detected(self) -> None:
        old_sigs = {
            "a": "old_signature_value_00000000000000000000000000001",
        }
        tables = [
            ExtractedTable(name="a", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
        ]
        changes = _detect_changes(previous_signatures=old_sigs, current_tables=tables)
        changed = [c for c in changes if c.change_type == SyncChangeType.CHANGED]
        assert len(changed) == 1
        assert changed[0].table.name == "a"
        assert changed[0].previous_signature == old_sigs["a"]

    def test_removed_detected(self) -> None:
        old_sigs = {
            "a": "sig_a",
            "b": "sig_b",
        }
        tables = [
            ExtractedTable(name="a", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
        ]
        changes = _detect_changes(previous_signatures=old_sigs, current_tables=tables)
        removed = [c for c in changes if c.change_type == SyncChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].table.name == "b"

    def test_mixed_changes(self) -> None:
        old_sigs = {
            "keep": "sig_keep",
            "remove": "sig_remove",
        }
        tables = [
            ExtractedTable(name="keep", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
            ExtractedTable(name="new", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
        ]
        sigs = _compute_signatures(tables)
        old_sigs["keep"] = sigs["keep"]
        changes = _detect_changes(previous_signatures=old_sigs, current_tables=tables, current_signatures=sigs)
        types = {c.change_type for c in changes}
        assert SyncChangeType.UNCHANGED in types
        assert SyncChangeType.ADDED in types
        assert SyncChangeType.REMOVED in types

    def test_removed_table_has_no_current_signature(self) -> None:
        old_sigs = {"gone": "sig_gone"}
        tables: list[ExtractedTable] = []
        changes = _detect_changes(previous_signatures=old_sigs, current_tables=tables)
        removed = [c for c in changes if c.change_type == SyncChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].current_signature is None
        assert removed[0].previous_signature == "sig_gone"

    def test_empty_previous_and_current(self) -> None:
        changes = _detect_changes(previous_signatures={}, current_tables=[])
        assert changes == []

    def test_previous_and_current_identical(self) -> None:
        tables = [
            ExtractedTable(name="a", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
        ]
        sigs = _compute_signatures(tables)
        changes = _detect_changes(previous_signatures=sigs, current_tables=tables, current_signatures=sigs)
        assert len(changes) == 1
        assert changes[0].change_type == SyncChangeType.UNCHANGED


# ---------------------------------------------------------------------------
# SyncResult
# ---------------------------------------------------------------------------

class TestSyncResult:
    def test_counts_empty(self) -> None:
        result = SyncResult(schema_info=ExtractedSchemaInfo(name="test", tables=[]))
        assert result.added_count == 0
        assert result.changed_count == 0
        assert result.removed_count == 0
        assert result.unchanged_count == 0

    def test_counts_correct(self) -> None:
        changes = [
            SyncChange(table=ExtractedTable(name="a", columns=[]), change_type=SyncChangeType.ADDED),
            SyncChange(table=ExtractedTable(name="b", columns=[]), change_type=SyncChangeType.CHANGED),
            SyncChange(table=ExtractedTable(name="c", columns=[]), change_type=SyncChangeType.REMOVED),
            SyncChange(table=ExtractedTable(name="d", columns=[]), change_type=SyncChangeType.UNCHANGED),
        ]
        result = SyncResult(schema_info=ExtractedSchemaInfo(name="test", tables=[]), changes=changes)
        assert result.added_count == 1
        assert result.changed_count == 1
        assert result.removed_count == 1
        assert result.unchanged_count == 1

    def test_synced_at_auto_set(self) -> None:
        result = SyncResult(schema_info=ExtractedSchemaInfo(name="test", tables=[]))
        assert isinstance(result.synced_at, datetime)
        assert result.synced_at.tzinfo is not None

    def test_errors_defaults_to_empty(self) -> None:
        result = SyncResult(schema_info=ExtractedSchemaInfo(name="test", tables=[]))
        assert result.errors == []


# ---------------------------------------------------------------------------
# SyncState
# ---------------------------------------------------------------------------

class TestSyncState:
    def test_defaults(self) -> None:
        state = SyncState()
        assert state.signatures == {}
        assert state.last_synced_at is None

    def test_with_signatures(self) -> None:
        state = SyncState(signatures={"a": "sig_a"}, last_synced_at=datetime(2026, 1, 1, tzinfo=UTC))
        assert state.signatures["a"] == "sig_a"
        assert state.last_synced_at is not None


# ---------------------------------------------------------------------------
# SyncChange
# ---------------------------------------------------------------------------

class TestSyncChange:
    def test_minimal(self) -> None:
        table = ExtractedTable(name="t", columns=[])
        change = SyncChange(table=table, change_type=SyncChangeType.ADDED)
        assert change.annotation is None
        assert change.relationships is None


# ---------------------------------------------------------------------------
# _filter_schemas
# ---------------------------------------------------------------------------

class TestFilterSchemas:
    def test_none_returns_all(self) -> None:
        schemas = [
            ExtractedSchemaInfo(name="public", tables=[]),
            ExtractedSchemaInfo(name="sales", tables=[]),
        ]
        result = _filter_schemas(schemas, None)
        assert len(result) == 2

    def test_filter_by_name(self) -> None:
        schemas = [
            ExtractedSchemaInfo(name="public", tables=[]),
            ExtractedSchemaInfo(name="sales", tables=[]),
        ]
        result = _filter_schemas(schemas, ["public"])
        assert len(result) == 1
        assert result[0].name == "public"

    def test_no_match_returns_empty(self) -> None:
        schemas = [
            ExtractedSchemaInfo(name="public", tables=[]),
        ]
        result = _filter_schemas(schemas, ["nonexistent"])
        assert result == []


# ---------------------------------------------------------------------------
# SyncOrchestrator
# ---------------------------------------------------------------------------

class TestSyncOrchestrator:
    def test_default_construction(self) -> None:
        orch = SyncOrchestrator()
        assert orch.state.signatures == {}
        assert orch.state.last_synced_at is None

    def test_reset_state(self) -> None:
        orch = SyncOrchestrator(sync_state=SyncState(signatures={"a": "sig"}))
        assert "a" in orch.state.signatures
        orch.reset_state()
        assert orch.state.signatures == {}

    async def test_sync_from_tables_empty(self) -> None:
        orch = SyncOrchestrator()
        result = await orch.sync_from_tables([])
        assert isinstance(result, SyncResult)
        assert len(result.changes) == 0
        assert result.added_count == 0

    async def test_sync_from_tables_detects_added(self) -> None:
        orch = SyncOrchestrator()
        tables = [
            ExtractedTable(
                name="users",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
            ),
        ]
        result = await orch.sync_from_tables(tables)
        assert result.added_count == 1
        assert result.changes[0].change_type == SyncChangeType.ADDED

    async def test_sync_from_tables_annotates(self) -> None:
        orch = SyncOrchestrator()
        tables = [
            ExtractedTable(
                name="users",
                columns=[ExtractedColumn(name="email", ordinal_position=1, data_type="VARCHAR", is_nullable=True)],
            ),
        ]
        result = await orch.sync_from_tables(tables, run_annotation=True, run_inference=False)
        added = [c for c in result.changes if c.change_type == SyncChangeType.ADDED]
        assert len(added) == 1
        if added[0].annotation is not None:
            assert added[0].annotation.table_name == "users"

    async def test_sync_from_tables_skips_annotation(self) -> None:
        orch = SyncOrchestrator()
        tables = [
            ExtractedTable(
                name="users",
                columns=[ExtractedColumn(name="email", ordinal_position=1, data_type="VARCHAR", is_nullable=True)],
            ),
        ]
        result = await orch.sync_from_tables(tables, run_annotation=False)
        added = [c for c in result.changes if c.change_type == SyncChangeType.ADDED]
        assert added[0].annotation is None

    async def test_sync_from_tables_runs_inference(self) -> None:
        orch = SyncOrchestrator()
        tables = [
            ExtractedTable(
                name="customers",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False, is_primary_key=True)],
            ),
            ExtractedTable(
                name="orders",
                columns=[ExtractedColumn(name="customer_id", ordinal_position=1, data_type="INT", is_nullable=True)],
            ),
        ]
        result = await orch.sync_from_tables(tables, run_annotation=False, run_inference=True)
        added = [c for c in result.changes if c.change_type == SyncChangeType.ADDED]
        has_rels = any(
            c.relationships is not None and len(c.relationships) > 0
            for c in added
        )
        assert has_rels

    async def test_sync_from_tables_incremental_second_call_unchanged(self) -> None:
        orch = SyncOrchestrator()
        tables = [
            ExtractedTable(
                name="users",
                columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
            ),
        ]
        await orch.sync_from_tables(tables, run_annotation=False, run_inference=False)
        result2 = await orch.sync_from_tables(tables, run_annotation=False, run_inference=False)
        assert result2.unchanged_count == 1
        assert result2.added_count == 0

    async def test_sync_from_tables_incremental_detects_change(self) -> None:
        orch = SyncOrchestrator()
        t1 = ExtractedTable(
            name="users",
            columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)],
        )
        await orch.sync_from_tables([t1], run_annotation=False, run_inference=False)

        t2 = ExtractedTable(
            name="users",
            columns=[
                ExtractedColumn(name="id", ordinal_position=1, data_type="BIGINT", is_nullable=False),
                ExtractedColumn(name="name", ordinal_position=2, data_type="VARCHAR(100)", is_nullable=True),
            ],
        )
        result2 = await orch.sync_from_tables([t2], run_annotation=False, run_inference=False)
        assert result2.changed_count == 1
        assert result2.unchanged_count == 0

    async def test_sync_from_tables_incremental_detects_removed(self) -> None:
        orch = SyncOrchestrator()
        tables = [
            ExtractedTable(name="a", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
            ExtractedTable(name="b", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
        ]
        await orch.sync_from_tables(tables, run_annotation=False, run_inference=False)
        result2 = await orch.sync_from_tables(
            [tables[0]], run_annotation=False, run_inference=False
        )
        assert result2.removed_count == 1
        assert result2.unchanged_count == 1

    async def test_sync_from_tables_preserves_state_across_calls(self) -> None:
        orch = SyncOrchestrator()
        tables = [
            ExtractedTable(name="x", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
        ]
        await orch.sync_from_tables(tables, run_annotation=False, run_inference=False)
        assert "x" in orch.state.signatures

    async def test_sync_from_tables_annotation_does_not_block_on_error(self) -> None:
        class FailingAnnotator:  # type: ignore
            async def annotate_batch(self, tables):  # type: ignore
                raise RuntimeError("LLM unavailable")

            async def annotate(self, table):  # type: ignore
                raise RuntimeError("LLM unavailable")

        orch = SyncOrchestrator()
        orch._annotation_service._annotator = FailingAnnotator()  # type: ignore
        tables = [
            ExtractedTable(name="users", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False)]),
        ]
        result = await orch.sync_from_tables(tables)
        assert result.added_count == 1
        added = [c for c in result.changes if c.change_type == SyncChangeType.ADDED]
        assert added[0].annotation is not None
        assert added[0].annotation.table_description == ""

    async def test_sync_from_tables_inference_errors_graceful(self) -> None:
        class FailingInferenceService:
            def infer(self, tables):  # type: ignore
                raise RuntimeError("inference failed")

        orch = SyncOrchestrator(inference_service=FailingInferenceService())  # type: ignore
        tables = [
            ExtractedTable(name="a", columns=[ExtractedColumn(name="id", ordinal_position=1, data_type="INT", is_nullable=False, is_primary_key=True)]),
        ]
        result = await orch.sync_from_tables(tables, run_annotation=False, run_inference=True)
        assert result.added_count == 1

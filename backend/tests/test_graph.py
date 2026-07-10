from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ke.models.graph import (
    GraphEdge as GraphEdgeModel,
)
from ke.models.graph import (
    GraphNode as GraphNodeModel,
)
from ke.models.graph import (
    GraphPath,
    OntologyExport,
    OntologyImport,
)
from ke.services.ontology import OntologyService
from ke.stores.graph.repository import (
    GraphEdgeOrm,
    GraphEdgeRepository,
    GraphNodeOrm,
    GraphNodeRepository,
    ORMBase,
)
from shared.models.pagination import PaginationParams


def _dt() -> datetime:
    return datetime.now(UTC)


_NOW = _dt()


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


class TestGraphNodeModel:
    def test_valid_node(self) -> None:
        node = GraphNodeModel(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            node_type="table",
            name="users",
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert node.name == "users"
        assert node.node_type == "table"
        assert node.properties == {}

    def test_all_node_types(self) -> None:
        for nt in ("table", "column", "domain", "concept", "glossary_term", "query_pattern"):
            node = GraphNodeModel(
                id=str(uuid4()),
                tenant_id=str(uuid4()),
                node_type=cast(Any, nt),
                name="x",
                created_at=_NOW,
                updated_at=_NOW,
            )
            assert node.node_type == nt

    def test_invalid_node_type(self) -> None:
        with pytest.raises(ValidationError):
            GraphNodeModel(
                id=str(uuid4()),
                tenant_id=str(uuid4()),
                node_type=cast(Any, "invalid_type"),
                name="x",
                created_at=_NOW,
                updated_at=_NOW,
            )

    def test_optional_fields(self) -> None:
        node = GraphNodeModel(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            node_type="concept",
            name="Revenue",
            description="Total revenue metric",
            external_id="ext-001",
            properties={"domain": "finance"},
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert node.description == "Total revenue metric"
        assert node.external_id == "ext-001"
        assert node.properties == {"domain": "finance"}

    def test_properties_default_empty_dict(self) -> None:
        node = GraphNodeModel(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            node_type="table",
            name="x",
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert node.properties == {}

    def test_from_attributes(self) -> None:
        data = {
            "id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "node_type": "domain",
            "external_id": None,
            "name": "Finance",
            "description": "Finance domain",
            "properties": {"owner": "fin-team"},
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        node = GraphNodeModel.model_validate(data, from_attributes=True)
        assert node.name == "Finance"
        assert node.node_type == "domain"

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            GraphNodeModel(
                id=str(uuid4()),
                tenant_id=str(uuid4()),
                node_type="table",
                created_at=_NOW,
                updated_at=_NOW,
            )

    def test_id_uuid_str_accepts_string(self) -> None:
        uid = str(uuid4())
        node = GraphNodeModel(
            id=uid,
            tenant_id=str(uuid4()),
            node_type="table",
            name="x",
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert node.id == uid

    def test_tenant_id_uuid_str(self) -> None:
        uid = str(uuid4())
        node = GraphNodeModel(
            id=str(uuid4()),
            tenant_id=uid,
            node_type="table",
            name="x",
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert node.tenant_id == uid


class TestGraphEdgeModel:
    def test_valid_edge(self) -> None:
        edge = GraphEdgeModel(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            source_node_id=str(uuid4()),
            target_node_id=str(uuid4()),
            edge_type="references",
            created_at=_NOW,
        )
        assert edge.edge_type == "references"
        assert edge.weight == 1.0

    def test_all_edge_types(self) -> None:
        for et in ("belongs_to", "references", "maps_to", "frequently_joined", "semantic_parent"):
            edge = GraphEdgeModel(
                id=str(uuid4()),
                tenant_id=str(uuid4()),
                source_node_id=str(uuid4()),
                target_node_id=str(uuid4()),
                edge_type=cast(Any, et),
                created_at=_NOW,
            )
            assert edge.edge_type == et

    def test_invalid_edge_type(self) -> None:
        with pytest.raises(ValidationError):
            GraphEdgeModel(
                id=str(uuid4()),
                tenant_id=str(uuid4()),
                source_node_id=str(uuid4()),
                target_node_id=str(uuid4()),
                edge_type=cast(Any, "invalid"),
                created_at=_NOW,
            )

    def test_custom_weight(self) -> None:
        edge = GraphEdgeModel(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            source_node_id=str(uuid4()),
            target_node_id=str(uuid4()),
            edge_type="frequently_joined",
            weight=2.5,
            created_at=_NOW,
        )
        assert edge.weight == 2.5

    def test_properties_default(self) -> None:
        edge = GraphEdgeModel(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            source_node_id=str(uuid4()),
            target_node_id=str(uuid4()),
            edge_type="maps_to",
            created_at=_NOW,
        )
        assert edge.properties == {}

    def test_from_attributes(self) -> None:
        data = {
            "id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "source_node_id": str(uuid4()),
            "target_node_id": str(uuid4()),
            "edge_type": "belongs_to",
            "weight": 1.0,
            "properties": {"cardinality": "many-to-one"},
            "created_at": _NOW,
        }
        edge = GraphEdgeModel.model_validate(data, from_attributes=True)
        assert edge.edge_type == "belongs_to"

    def test_source_and_target_required(self) -> None:
        with pytest.raises(ValidationError):
            GraphEdgeModel(
                id=str(uuid4()),
                tenant_id=str(uuid4()),
                edge_type="references",
                created_at=_NOW,
            )


class TestGraphPath:
    def test_empty_path(self) -> None:
        path = GraphPath(nodes=[], edges=[])
        assert path.nodes == []
        assert path.edges == []
        assert path.total_weight == 0.0
        assert path.depth == 0

    def test_path_with_items(self) -> None:
        node = GraphNodeModel(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            node_type="table",
            name="orders",
            created_at=_NOW,
            updated_at=_NOW,
        )
        edge = GraphEdgeModel(
            id=str(uuid4()),
            tenant_id=str(uuid4()),
            source_node_id=str(uuid4()),
            target_node_id=str(uuid4()),
            edge_type="references",
            created_at=_NOW,
        )
        path = GraphPath(nodes=[node], edges=[edge], total_weight=1.5, depth=1)
        assert len(path.nodes) == 1
        assert len(path.edges) == 1
        assert path.total_weight == 1.5
        assert path.depth == 1


class TestOntologyImport:
    def test_valid_import_merge_default(self) -> None:
        imp = OntologyImport(
            nodes=[{"id": "n1", "name": "N1"}],
            edges=[{"source": "n1", "target": "n2"}],
        )
        assert imp.mode == "merge"

    def test_valid_import_replace(self) -> None:
        imp = OntologyImport(nodes=[], edges=[], mode="replace")
        assert imp.mode == "replace"

    def test_invalid_mode(self) -> None:
        with pytest.raises(ValidationError):
            OntologyImport(nodes=[], edges=[], mode=cast(Any, "delete"))


class TestOntologyExport:
    def test_valid_export_json_default(self) -> None:
        exp = OntologyExport(tenant_id=str(uuid4()))
        assert exp.format == "json"
        assert exp.node_types is None

    def test_valid_export_with_filters(self) -> None:
        exp = OntologyExport(
            tenant_id=str(uuid4()),
            node_types=["table", "column"],
            format="yaml",
        )
        assert exp.node_types == ["table", "column"]
        assert exp.format == "yaml"

    def test_invalid_format(self) -> None:
        with pytest.raises(ValidationError):
            OntologyExport(tenant_id=str(uuid4()), format=cast(Any, "xml"))


# ---------------------------------------------------------------------------
# Repository Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_result() -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    result.scalar.return_value = 0
    result.fetchall.return_value = []
    return result


@pytest.fixture
def mock_session(mock_result: MagicMock) -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = mock_result
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


class TestORMBase:
    def test_orm_base_importable(self) -> None:
        assert ORMBase is not None

    def test_graph_node_orm_columns(self) -> None:
        cols = {c.name for c in GraphNodeOrm.__table__.columns}
        expected = {
            "id",
            "tenant_id",
            "node_type",
            "external_id",
            "name",
            "description",
            "properties",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(cols)

    def test_graph_node_orm_schema(self) -> None:
        assert GraphNodeOrm.__table_args__["schema"] == "graph_store"

    def test_graph_edge_orm_columns(self) -> None:
        cols = {c.name for c in GraphEdgeOrm.__table__.columns}
        expected = {
            "id",
            "tenant_id",
            "source_node_id",
            "target_node_id",
            "edge_type",
            "weight",
            "properties",
            "created_at",
        }
        assert expected.issubset(cols)

    def test_graph_edge_orm_schema(self) -> None:
        assert GraphEdgeOrm.__table_args__["schema"] == "graph_store"


class TestGraphNodeRepository:
    def test_instantiation(self, mock_session: AsyncMock) -> None:
        repo = GraphNodeRepository(session=mock_session)
        assert repo._session is mock_session

    def test_has_crud_methods(self, mock_session: AsyncMock) -> None:
        repo = GraphNodeRepository(session=mock_session)
        assert hasattr(repo, "get")
        assert hasattr(repo, "list")
        assert hasattr(repo, "create")
        assert hasattr(repo, "update")
        assert hasattr(repo, "delete")

    async def test_get_returns_none_for_missing(self, mock_session: AsyncMock) -> None:
        repo = GraphNodeRepository(session=mock_session)
        result = await repo.get("non-existent")
        assert result is None

    async def test_get_returns_node_when_found(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        uid = str(uuid4())
        mock_orm = MagicMock()
        mock_orm.id = uid
        mock_orm.tenant_id = str(uuid4())
        mock_orm.node_type = "table"
        mock_orm.external_id = None
        mock_orm.name = "users"
        mock_orm.description = "Users table"
        mock_orm.properties = {}
        mock_orm.created_at = _NOW
        mock_orm.updated_at = _NOW
        mock_result.scalar_one_or_none.return_value = mock_orm

        repo = GraphNodeRepository(session=mock_session)
        result = await repo.get(uid)
        assert result is not None
        assert result.name == "users"
        assert result.node_type == "table"

    async def test_list_returns_empty(self, mock_session: AsyncMock) -> None:
        repo = GraphNodeRepository(session=mock_session)
        items, total = await repo.list()
        assert items == []
        assert total == 0

    async def test_list_with_filter(self, mock_session: AsyncMock, mock_result: MagicMock) -> None:
        uid = str(uuid4())
        mock_orm = MagicMock()
        mock_orm.id = uid
        mock_orm.tenant_id = str(uuid4())
        mock_orm.node_type = "table"
        mock_orm.external_id = None
        mock_orm.name = "users"
        mock_orm.description = None
        mock_orm.properties = {}
        mock_orm.created_at = _NOW
        mock_orm.updated_at = _NOW
        mock_result.scalars.return_value.all.return_value = [mock_orm]
        mock_result.scalar.return_value = 1

        repo = GraphNodeRepository(session=mock_session)
        items, total = await repo.list(tenant_id=str(uuid4()), node_type="table")
        assert len(items) == 1
        assert total == 1
        assert items[0].name == "users"

    async def test_list_with_pagination(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        mock_result.scalar.return_value = 0
        repo = GraphNodeRepository(session=mock_session)
        items, total = await repo.list(pagination=PaginationParams(page=2, page_size=10))
        assert items == []
        assert total == 0

    async def test_create_returns_node(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        uid = str(uuid4())
        mock_orm = MagicMock()
        mock_orm.id = uid
        mock_orm.tenant_id = str(uuid4())
        mock_orm.node_type = "domain"
        mock_orm.external_id = None
        mock_orm.name = "Finance"
        mock_orm.description = None
        mock_orm.properties = {}
        mock_orm.created_at = _NOW
        mock_orm.updated_at = _NOW
        mock_result.scalar_one_or_none.return_value = mock_orm

        repo = GraphNodeRepository(session=mock_session)
        result = await repo.create(
            {
                "tenant_id": str(uuid4()),
                "node_type": "domain",
                "name": "Finance",
                "properties": {},
                "created_at": _NOW,
                "updated_at": _NOW,
            }
        )
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()
        assert result.name == "Finance"
        assert result.node_type == "domain"

    async def test_update_returns_updated_node(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        uid = str(uuid4())
        mock_orm = MagicMock()
        mock_orm.id = uid
        mock_orm.tenant_id = str(uuid4())
        mock_orm.node_type = "domain"
        mock_orm.external_id = None
        mock_orm.name = "Old Name"
        mock_orm.description = None
        mock_orm.properties = {}
        mock_orm.created_at = _NOW
        mock_orm.updated_at = _NOW

        updated_orm = MagicMock()
        updated_orm.id = uid
        updated_orm.tenant_id = str(uuid4())
        updated_orm.node_type = "domain"
        updated_orm.external_id = None
        updated_orm.name = "New Name"
        updated_orm.description = "Updated"
        updated_orm.properties = {}
        updated_orm.created_at = _NOW
        updated_orm.updated_at = _NOW

        mock_result.scalar_one_or_none.side_effect = [mock_orm, updated_orm]

        repo = GraphNodeRepository(session=mock_session)
        result = await repo.update(uid, {"name": "New Name", "description": "Updated"})
        assert result is not None
        assert mock_session.flush.awaited

    async def test_update_returns_none_for_missing(self, mock_session: AsyncMock) -> None:
        repo = GraphNodeRepository(session=mock_session)
        result = await repo.update("non-existent", {"name": "X"})
        assert result is None

    async def test_delete_returns_true_when_deleted(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        mock_result.scalar_one_or_none.return_value = MagicMock()
        repo = GraphNodeRepository(session=mock_session)
        result = await repo.delete("existing-id")
        assert result is True
        mock_session.delete.assert_called_once()
        mock_session.flush.assert_awaited_once()

    async def test_delete_returns_false_for_missing(self, mock_session: AsyncMock) -> None:
        repo = GraphNodeRepository(session=mock_session)
        result = await repo.delete("non-existent")
        assert result is False


class TestGraphEdgeRepository:
    def test_instantiation(self, mock_session: AsyncMock) -> None:
        repo = GraphEdgeRepository(session=mock_session)
        assert repo._session is mock_session

    def test_has_crud_methods(self, mock_session: AsyncMock) -> None:
        repo = GraphEdgeRepository(session=mock_session)
        assert hasattr(repo, "get")
        assert hasattr(repo, "list")
        assert hasattr(repo, "create")
        assert hasattr(repo, "update")
        assert hasattr(repo, "delete")
        assert hasattr(repo, "traverse")

    async def test_get_returns_none_for_missing(self, mock_session: AsyncMock) -> None:
        repo = GraphEdgeRepository(session=mock_session)
        result = await repo.get("non-existent")
        assert result is None

    async def test_get_returns_edge_when_found(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        uid = str(uuid4())
        mock_orm = MagicMock()
        mock_orm.id = uid
        mock_orm.tenant_id = str(uuid4())
        mock_orm.source_node_id = str(uuid4())
        mock_orm.target_node_id = str(uuid4())
        mock_orm.edge_type = "references"
        mock_orm.weight = 1.0
        mock_orm.properties = {}
        mock_orm.created_at = _NOW
        mock_result.scalar_one_or_none.return_value = mock_orm

        repo = GraphEdgeRepository(session=mock_session)
        result = await repo.get(uid)
        assert result is not None
        assert result.edge_type == "references"
        assert result.weight == 1.0

    async def test_list_returns_empty(self, mock_session: AsyncMock) -> None:
        repo = GraphEdgeRepository(session=mock_session)
        items, total = await repo.list()
        assert items == []
        assert total == 0

    async def test_list_with_multiple_filters(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        mock_orm = MagicMock()
        mock_orm.id = str(uuid4())
        mock_orm.tenant_id = str(uuid4())
        mock_orm.source_node_id = str(uuid4())
        mock_orm.target_node_id = str(uuid4())
        mock_orm.edge_type = "references"
        mock_orm.weight = 1.0
        mock_orm.properties = {}
        mock_orm.created_at = _NOW
        mock_result.scalars.return_value.all.return_value = [mock_orm]
        mock_result.scalar.return_value = 1

        repo = GraphEdgeRepository(session=mock_session)
        items, total = await repo.list(
            tenant_id=str(uuid4()),
            source_node_id=str(uuid4()),
            edge_type="references",
        )
        assert len(items) == 1
        assert total == 1

    async def test_create_returns_edge(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        uid = str(uuid4())
        mock_orm = MagicMock()
        mock_orm.id = uid
        mock_orm.tenant_id = str(uuid4())
        mock_orm.source_node_id = str(uuid4())
        mock_orm.target_node_id = str(uuid4())
        mock_orm.edge_type = "frequently_joined"
        mock_orm.weight = 2.0
        mock_orm.properties = {}
        mock_orm.created_at = _NOW
        mock_result.scalar_one_or_none.return_value = mock_orm

        repo = GraphEdgeRepository(session=mock_session)
        result = await repo.create(
            {
                "tenant_id": str(uuid4()),
                "source_node_id": str(uuid4()),
                "target_node_id": str(uuid4()),
                "edge_type": "frequently_joined",
                "weight": 2.0,
                "properties": {},
                "created_at": _NOW,
            }
        )
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()
        assert result.edge_type == "frequently_joined"
        assert result.weight == 2.0

    async def test_update_returns_none_for_missing(self, mock_session: AsyncMock) -> None:
        repo = GraphEdgeRepository(session=mock_session)
        result = await repo.update("non-existent", {"weight": 3.0})
        assert result is None

    async def test_delete_returns_false_for_missing(self, mock_session: AsyncMock) -> None:
        repo = GraphEdgeRepository(session=mock_session)
        result = await repo.delete("non-existent")
        assert result is False

    async def test_traverse_returns_empty_when_no_paths(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        mock_result.fetchall.return_value = []
        repo = GraphEdgeRepository(session=mock_session)
        paths = await repo.traverse(
            start_node_id=str(uuid4()),
            end_node_id=str(uuid4()),
        )
        assert paths == []

    async def test_traverse_returns_paths(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        edge_id = str(uuid4())
        node_a = str(uuid4())
        node_b = str(uuid4())
        mock_result.fetchall.return_value = [
            ([edge_id], [node_a, node_b], 1.0, 1),
        ]
        mock_edge_orm = MagicMock()
        mock_edge_orm.id = edge_id
        mock_edge_orm.tenant_id = str(uuid4())
        mock_edge_orm.source_node_id = node_a
        mock_edge_orm.target_node_id = node_b
        mock_edge_orm.edge_type = "references"
        mock_edge_orm.weight = 1.0
        mock_edge_orm.properties = {}
        mock_edge_orm.created_at = _NOW

        mock_node_orm_a = MagicMock()
        mock_node_orm_a.id = node_a
        mock_node_orm_a.tenant_id = str(uuid4())
        mock_node_orm_a.node_type = "table"
        mock_node_orm_a.external_id = None
        mock_node_orm_a.name = "orders"
        mock_node_orm_a.description = None
        mock_node_orm_a.properties = {}
        mock_node_orm_a.created_at = _NOW
        mock_node_orm_a.updated_at = _NOW

        mock_node_orm_b = MagicMock()
        mock_node_orm_b.id = node_b
        mock_node_orm_b.tenant_id = str(uuid4())
        mock_node_orm_b.node_type = "table"
        mock_node_orm_b.external_id = None
        mock_node_orm_b.name = "customers"
        mock_node_orm_b.description = None
        mock_node_orm_b.properties = {}
        mock_node_orm_b.created_at = _NOW
        mock_node_orm_b.updated_at = _NOW

        class SideEffectExecute:
            def __init__(self, mock_result_obj):
                self.call_count = 0
                self.mock_result = mock_result_obj

            async def __call__(self, stmt, *args, **kwargs):
                self.call_count += 1
                if self.call_count == 1:
                    return self.mock_result
                elif self.call_count == 2:
                    r2 = MagicMock()
                    r2.scalars.return_value.all.return_value = [mock_node_orm_a, mock_node_orm_b]
                    return r2
                else:
                    r3 = MagicMock()
                    r3.scalars.return_value.all.return_value = [mock_edge_orm]
                    return r3

        mock_session.execute = SideEffectExecute(mock_result)

        repo = GraphEdgeRepository(session=mock_session)
        paths = await repo.traverse(start_node_id=node_a, max_depth=3)
        assert len(paths) == 1
        assert paths[0].depth == 1
        assert paths[0].total_weight == 1.0
        assert len(paths[0].nodes) == 2
        assert len(paths[0].edges) == 1

    async def test_traverse_with_edge_types_filter(
        self, mock_session: AsyncMock, mock_result: MagicMock
    ) -> None:
        mock_result.fetchall.return_value = []
        repo = GraphEdgeRepository(session=mock_session)
        paths = await repo.traverse(
            start_node_id=str(uuid4()),
            edge_types=["references", "frequently_joined"],
        )
        assert paths == []


def _make_node(overrides: dict | None = None) -> GraphNodeModel:
    data = {
        "id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "node_type": "table",
        "external_id": None,
        "name": "test_node",
        "description": None,
        "properties": {},
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    if overrides:
        data.update(overrides)
    return GraphNodeModel.model_validate(data, from_attributes=True)


def _make_edge(overrides: dict | None = None) -> GraphEdgeModel:
    data = {
        "id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "source_node_id": str(uuid4()),
        "target_node_id": str(uuid4()),
        "edge_type": "references",
        "weight": 1.0,
        "properties": {},
        "created_at": _NOW,
    }
    if overrides:
        data.update(overrides)
    return GraphEdgeModel.model_validate(data, from_attributes=True)


class TestOntologyService:
    async def test_import_replace_deletes_existing(self) -> None:
        tenant_id = str(uuid4())
        node_repo = AsyncMock(spec=GraphNodeRepository)
        edge_repo = AsyncMock(spec=GraphEdgeRepository)
        node_repo.delete_all_for_tenant = AsyncMock(return_value=2)
        edge_repo.delete_all_for_tenant = AsyncMock(return_value=3)
        node_repo.create = AsyncMock(return_value=_make_node({"id": str(uuid4()), "name": "n1"}))

        svc = OntologyService(node_repo=node_repo, edge_repo=edge_repo)
        result = await svc.import_ontology(
            tenant_id=tenant_id,
            data=OntologyImport(
                mode="replace",
                nodes=[{"name": "n1", "node_type": "table"}],
                edges=[],
            ),
        )
        edge_repo.delete_all_for_tenant.assert_awaited_once_with(tenant_id)
        node_repo.delete_all_for_tenant.assert_awaited_once_with(tenant_id)
        assert result.nodes_created == 1

    async def test_import_merge_updates_existing(self) -> None:
        tenant_id = str(uuid4())
        existing = _make_node({"external_id": "ext-1", "name": "old_name"})
        node_repo = AsyncMock(spec=GraphNodeRepository)
        edge_repo = AsyncMock(spec=GraphEdgeRepository)
        node_repo.get_by_external_id = AsyncMock(return_value=existing)
        updated = _make_node({"id": existing.id, "name": "new_name"})
        node_repo.update = AsyncMock(return_value=updated)

        svc = OntologyService(node_repo=node_repo, edge_repo=edge_repo)
        result = await svc.import_ontology(
            tenant_id=tenant_id,
            data=OntologyImport(
                mode="merge",
                nodes=[{
                    "external_id": "ext-1",
                    "name": "new_name",
                    "node_type": "table",
                }],
                edges=[],
            ),
        )
        node_repo.get_by_external_id.assert_awaited_once_with(tenant_id, "ext-1")
        assert result.nodes_updated == 1
        assert result.nodes_created == 0

    async def test_import_merge_creates_new(self) -> None:
        tenant_id = str(uuid4())
        node_repo = AsyncMock(spec=GraphNodeRepository)
        edge_repo = AsyncMock(spec=GraphEdgeRepository)
        node_repo.get_by_external_id = AsyncMock(return_value=None)
        node_repo.create = AsyncMock(return_value=_make_node({"id": str(uuid4()), "name": "n1"}))

        svc = OntologyService(node_repo=node_repo, edge_repo=edge_repo)
        result = await svc.import_ontology(
            tenant_id=tenant_id,
            data=OntologyImport(
                mode="merge",
                nodes=[{"external_id": "ext-new", "name": "n1", "node_type": "table"}],
                edges=[],
            ),
        )
        assert result.nodes_created == 1
        assert result.nodes_updated == 0

    async def test_import_creates_edges_with_node_id_mapping(self) -> None:
        tenant_id = str(uuid4())
        created_node = _make_node({"id": "node-uuid-1", "name": "n1"})
        node_repo = AsyncMock(spec=GraphNodeRepository)
        edge_repo = AsyncMock(spec=GraphEdgeRepository)
        node_repo.get_by_external_id = AsyncMock(return_value=None)
        node_repo.create = AsyncMock(return_value=created_node)
        edge_repo.create = AsyncMock(return_value=_make_edge())

        svc = OntologyService(node_repo=node_repo, edge_repo=edge_repo)
        result = await svc.import_ontology(
            tenant_id=tenant_id,
            data=OntologyImport(
                mode="merge",
                nodes=[{"external_id": "n1", "name": "n1", "node_type": "table"}],
                edges=[{
                    "source_node_id": "n1",
                    "target_node_id": "n1",
                    "edge_type": "references",
                }],
            ),
        )
        assert result.nodes_created == 1
        assert result.edges_created == 1
        edge_repo.create.assert_awaited_once()
        assert edge_repo.create.await_args.args[0]["source_node_id"] == "node-uuid-1"

    async def test_export_json(self) -> None:
        tenant_id = str(uuid4())
        node = _make_node({"tenant_id": tenant_id, "name": "orders", "node_type": "table"})
        edge = _make_edge({
            "tenant_id": tenant_id,
            "source_node_id": node.id,
            "target_node_id": node.id,
        })
        node_repo = AsyncMock(spec=GraphNodeRepository)
        edge_repo = AsyncMock(spec=GraphEdgeRepository)
        node_repo.list_all_for_tenant = AsyncMock(return_value=[node])
        edge_repo.list_all_for_tenant = AsyncMock(return_value=[edge])

        svc = OntologyService(node_repo=node_repo, edge_repo=edge_repo)
        output = await svc.export_ontology(
            tenant_id=tenant_id,
            params=OntologyExport(tenant_id=tenant_id, format="json"),
        )
        assert '"name": "orders"' in output
        assert '"node_type": "table"' in output

    async def test_export_yaml(self) -> None:
        tenant_id = str(uuid4())
        node = _make_node({"tenant_id": tenant_id, "name": "orders", "node_type": "table"})
        node_repo = AsyncMock(spec=GraphNodeRepository)
        edge_repo = AsyncMock(spec=GraphEdgeRepository)
        node_repo.list_all_for_tenant = AsyncMock(return_value=[node])
        edge_repo.list_all_for_tenant = AsyncMock(return_value=[])

        svc = OntologyService(node_repo=node_repo, edge_repo=edge_repo)
        output = await svc.export_ontology(
            tenant_id=tenant_id,
            params=OntologyExport(tenant_id=tenant_id, format="yaml"),
        )
        assert "name: orders" in output
        assert "node_type: table" in output

    async def test_export_filters_by_node_type(self) -> None:
        tenant_id = str(uuid4())
        table_node = _make_node({
            "tenant_id": tenant_id,
            "name": "orders",
            "node_type": "table",
            "id": str(uuid4()),
        })
        node_repo = AsyncMock(spec=GraphNodeRepository)
        edge_repo = AsyncMock(spec=GraphEdgeRepository)
        node_repo.list_all_for_tenant = AsyncMock(return_value=[table_node])
        edge_repo.list_all_for_tenant = AsyncMock(return_value=[])

        svc = OntologyService(node_repo=node_repo, edge_repo=edge_repo)
        output = await svc.export_ontology(
            tenant_id=tenant_id,
            params=OntologyExport(tenant_id=tenant_id, node_types=["table"], format="json"),
        )
        assert '"name": "orders"' in output
        assert '"name": "revenue"' not in output
        node_repo.list_all_for_tenant.assert_awaited_once_with(
            tenant_id=tenant_id,
            node_types=["table"],
        )

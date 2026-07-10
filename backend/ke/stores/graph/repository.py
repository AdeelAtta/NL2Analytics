from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column as SAColumn
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, and_, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from ke.models.graph import GraphEdge as GraphEdgeModel
from ke.models.graph import GraphNode as GraphNodeModel
from ke.models.graph import GraphPath, NodeType
from shared.models.pagination import PaginationParams


class ORMBase(DeclarativeBase):
    pass


class GraphNodeOrm(ORMBase):
    __tablename__ = "graph_nodes"
    __table_args__ = {"schema": "graph_store"}

    id = SAColumn(PG_UUID(), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = SAColumn(
        PG_UUID(), ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False
    )
    node_type = SAColumn(String(50), nullable=False)
    external_id = SAColumn(String(255), nullable=True)
    name = SAColumn(String(500), nullable=False)
    description = SAColumn(Text(), nullable=True)
    properties = SAColumn(JSONB(), nullable=False, server_default=text("'{}'::jsonb"))
    created_at = SAColumn(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = SAColumn(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class GraphEdgeOrm(ORMBase):
    __tablename__ = "graph_edges"
    __table_args__ = {"schema": "graph_store"}

    id = SAColumn(PG_UUID(), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = SAColumn(
        PG_UUID(), ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False
    )
    source_node_id = SAColumn(
        PG_UUID(), ForeignKey("graph_store.graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_node_id = SAColumn(
        PG_UUID(), ForeignKey("graph_store.graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    edge_type = SAColumn(String(50), nullable=False)
    weight = SAColumn(Float(), nullable=False, server_default=text("1.0"))
    properties = SAColumn(JSONB(), nullable=False, server_default=text("'{}'::jsonb"))
    created_at = SAColumn(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


class GraphNodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, node_id: str) -> GraphNodeModel | None:
        stmt = select(GraphNodeOrm).where(GraphNodeOrm.id == node_id)
        result = await self._session.execute(stmt)
        instance = result.scalar_one_or_none()
        if instance is None:
            return None
        return GraphNodeModel.model_validate(instance, from_attributes=True)

    async def list(
        self,
        tenant_id: str | None = None,
        node_type: str | None = None,
        pagination: PaginationParams | None = None,
    ) -> tuple[list[GraphNodeModel], int]:
        conditions = []
        if tenant_id:
            conditions.append(GraphNodeOrm.tenant_id == tenant_id)
        if node_type:
            conditions.append(GraphNodeOrm.node_type == node_type)

        query = select(GraphNodeOrm)
        count_query = select(func.count()).select_from(GraphNodeOrm)
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        total_result = await self._session.execute(count_query)
        total = total_result.scalar() or 0

        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
            query = query.offset(offset).limit(pagination.page_size)

        result = await self._session.execute(query)
        instances = result.scalars().all()
        items = [GraphNodeModel.model_validate(inst, from_attributes=True) for inst in instances]
        return items, int(total)

    async def create(self, data: dict[str, Any]) -> GraphNodeModel:
        instance = GraphNodeOrm(**data)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return GraphNodeModel.model_validate(instance, from_attributes=True)

    async def update(self, node_id: str, data: dict[str, Any]) -> GraphNodeModel | None:
        stmt = select(GraphNodeOrm).where(GraphNodeOrm.id == node_id)
        result = await self._session.execute(stmt)
        instance = result.scalar_one_or_none()
        if instance is None:
            return None
        data.pop("id", None)
        data.pop("created_at", None)
        data["updated_at"] = datetime.now(UTC)
        for key, value in data.items():
            setattr(instance, key, value)
        await self._session.flush()
        await self._session.refresh(instance)
        return GraphNodeModel.model_validate(instance, from_attributes=True)

    async def delete(self, node_id: str) -> bool:
        stmt = select(GraphNodeOrm).where(GraphNodeOrm.id == node_id)
        result = await self._session.execute(stmt)
        instance = result.scalar_one_or_none()
        if instance is None:
            return False
        await self._session.delete(instance)
        await self._session.flush()
        return True

    async def get_by_external_id(self, tenant_id: str, external_id: str) -> GraphNodeModel | None:
        stmt = select(GraphNodeOrm).where(
            GraphNodeOrm.tenant_id == tenant_id,
            GraphNodeOrm.external_id == external_id,
        )
        result = await self._session.execute(stmt)
        instance = result.scalar_one_or_none()
        if instance is None:
            return None
        return GraphNodeModel.model_validate(instance, from_attributes=True)

    async def delete_all_for_tenant(self, tenant_id: str) -> int:
        stmt = select(GraphNodeOrm).where(GraphNodeOrm.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        instances = result.scalars().all()
        count = len(instances)
        for inst in instances:
            await self._session.delete(inst)
        if count:
            await self._session.flush()
        return count

    async def list_all_for_tenant(
        self,
        tenant_id: str,
        node_types: list[NodeType] | None = None,
    ) -> list[GraphNodeModel]:
        conditions = [GraphNodeOrm.tenant_id == tenant_id]
        if node_types:
            conditions.append(GraphNodeOrm.node_type.in_(node_types))
        stmt = select(GraphNodeOrm).where(and_(*conditions))
        result = await self._session.execute(stmt)
        instances = result.scalars().all()
        return [GraphNodeModel.model_validate(inst, from_attributes=True) for inst in instances]


class GraphEdgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, edge_id: str) -> GraphEdgeModel | None:
        stmt = select(GraphEdgeOrm).where(GraphEdgeOrm.id == edge_id)
        result = await self._session.execute(stmt)
        instance = result.scalar_one_or_none()
        if instance is None:
            return None
        return GraphEdgeModel.model_validate(instance, from_attributes=True)

    async def list(
        self,
        tenant_id: str | None = None,
        source_node_id: str | None = None,
        target_node_id: str | None = None,
        edge_type: str | None = None,
        pagination: PaginationParams | None = None,
    ) -> tuple[list[GraphEdgeModel], int]:
        conditions = []
        if tenant_id:
            conditions.append(GraphEdgeOrm.tenant_id == tenant_id)
        if source_node_id:
            conditions.append(GraphEdgeOrm.source_node_id == source_node_id)
        if target_node_id:
            conditions.append(GraphEdgeOrm.target_node_id == target_node_id)
        if edge_type:
            conditions.append(GraphEdgeOrm.edge_type == edge_type)

        query = select(GraphEdgeOrm)
        count_query = select(func.count()).select_from(GraphEdgeOrm)
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        total_result = await self._session.execute(count_query)
        total = total_result.scalar() or 0

        if pagination:
            offset = (pagination.page - 1) * pagination.page_size
            query = query.offset(offset).limit(pagination.page_size)

        result = await self._session.execute(query)
        instances = result.scalars().all()
        items = [GraphEdgeModel.model_validate(inst, from_attributes=True) for inst in instances]
        return items, int(total)

    async def create(self, data: dict[str, Any]) -> GraphEdgeModel:
        instance = GraphEdgeOrm(**data)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return GraphEdgeModel.model_validate(instance, from_attributes=True)

    async def update(self, edge_id: str, data: dict[str, Any]) -> GraphEdgeModel | None:
        stmt = select(GraphEdgeOrm).where(GraphEdgeOrm.id == edge_id)
        result = await self._session.execute(stmt)
        instance = result.scalar_one_or_none()
        if instance is None:
            return None
        data.pop("id", None)
        data.pop("created_at", None)
        for key, value in data.items():
            setattr(instance, key, value)
        await self._session.flush()
        await self._session.refresh(instance)
        return GraphEdgeModel.model_validate(instance, from_attributes=True)

    async def delete(self, edge_id: str) -> bool:
        stmt = select(GraphEdgeOrm).where(GraphEdgeOrm.id == edge_id)
        result = await self._session.execute(stmt)
        instance = result.scalar_one_or_none()
        if instance is None:
            return False
        await self._session.delete(instance)
        await self._session.flush()
        return True

    async def delete_all_for_tenant(self, tenant_id: str) -> int:
        stmt = select(GraphEdgeOrm).where(GraphEdgeOrm.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        instances = result.scalars().all()
        count = len(instances)
        for inst in instances:
            await self._session.delete(inst)
        if count:
            await self._session.flush()
        return count

    async def list_all_for_tenant(
        self,
        tenant_id: str,
    ) -> list[GraphEdgeModel]:
        stmt = select(GraphEdgeOrm).where(GraphEdgeOrm.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        instances = result.scalars().all()
        return [GraphEdgeModel.model_validate(inst, from_attributes=True) for inst in instances]

    async def traverse(
        self,
        start_node_id: str,
        end_node_id: str | None = None,
        max_depth: int = 5,
        edge_types: list[str] | None = None,
    ) -> list[GraphPath]:
        edge_filter = ""
        if edge_types:
            quoted = [f"'{et}'" for et in edge_types]
            edge_filter = f"AND e.edge_type IN ({', '.join(quoted)})"

        query = text(f"""
            WITH RECURSIVE path AS (
                SELECT
                    e.id AS edge_id,
                    e.source_node_id,
                    e.target_node_id,
                    e.edge_type,
                    e.weight,
                    1 AS depth,
                    ARRAY[e.source_node_id, e.target_node_id] AS node_ids,
                    ARRAY[e.id] AS edge_ids,
                    e.weight AS total_weight
                FROM graph_store.graph_edges e
                WHERE e.source_node_id = :start_id {edge_filter}

                UNION ALL

                SELECT
                    e.id,
                    e.source_node_id,
                    e.target_node_id,
                    e.edge_type,
                    e.weight,
                    p.depth + 1,
                    p.node_ids || e.target_node_id,
                    p.edge_ids || e.id,
                    p.total_weight + e.weight
                FROM graph_store.graph_edges e
                INNER JOIN path p ON e.source_node_id = p.target_node_id
                WHERE p.depth < :max_depth
                  {edge_filter}
                  AND NOT (e.target_node_id = ANY(p.node_ids))
            )
            SELECT DISTINCT ON (p.node_ids, p.edge_ids)
                p.edge_ids,
                p.node_ids,
                p.total_weight,
                p.depth
            FROM path p
            WHERE (:end_id IS NULL OR p.target_node_id = :end_id)
            ORDER BY p.node_ids, p.edge_ids, p.total_weight ASC
            LIMIT 50
        """)

        result = await self._session.execute(
            query,
            {"start_id": start_node_id, "end_id": end_node_id, "max_depth": max_depth},
        )
        rows = result.fetchall()

        paths: list[GraphPath] = []
        for row in rows:
            edge_ids = row[0]
            node_ids = row[1]
            total_weight = float(row[2])
            depth = int(row[3])

            node_stmt = select(GraphNodeOrm).where(GraphNodeOrm.id.in_(node_ids))
            node_result = await self._session.execute(node_stmt)
            nodes = [
                GraphNodeModel.model_validate(n, from_attributes=True)
                for n in node_result.scalars().all()
            ]

            edge_stmt = select(GraphEdgeOrm).where(GraphEdgeOrm.id.in_(edge_ids))
            edge_result = await self._session.execute(edge_stmt)
            edges = [
                GraphEdgeModel.model_validate(e, from_attributes=True)
                for e in edge_result.scalars().all()
            ]

            paths.append(
                GraphPath(nodes=nodes, edges=edges, total_weight=total_weight, depth=depth)
            )

        return paths

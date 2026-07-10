from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import yaml

from ke.models.graph import (
    GraphNode as GraphNodeModel,
)
from ke.models.graph import (
    OntologyExport,
    OntologyImport,
)
from ke.stores.graph.repository import GraphEdgeRepository, GraphNodeRepository


class OntologyImportResult:
    nodes_created: int = 0
    nodes_updated: int = 0
    edges_created: int = 0
    edges_updated: int = 0


class OntologyService:
    def __init__(
        self,
        node_repo: GraphNodeRepository,
        edge_repo: GraphEdgeRepository,
    ) -> None:
        self._node_repo = node_repo
        self._edge_repo = edge_repo

    async def import_ontology(
        self,
        tenant_id: str,
        data: OntologyImport,
    ) -> OntologyImportResult:
        result = OntologyImportResult()

        if data.mode == "replace":
            await self._edge_repo.delete_all_for_tenant(tenant_id)
            await self._node_repo.delete_all_for_tenant(tenant_id)

        now = datetime.now(UTC)

        node_id_map: dict[str, str] = {}
        for node_data in data.nodes:
            external_id = node_data.get("external_id")
            existing: GraphNodeModel | None = None
            if external_id and data.mode == "merge":
                existing = await self._node_repo.get_by_external_id(tenant_id, external_id)

            if existing:
                update_data = {
                    k: v
                    for k, v in node_data.items()
                    if k not in ("id", "external_id", "created_at", "updated_at")
                }
                updated = await self._node_repo.update(existing.id, update_data)
                if updated:
                    result.nodes_updated += 1
                node_id_map[external_id or str(node_data.get("id", ""))] = existing.id
            else:
                create_data: dict[str, Any] = {
                    "tenant_id": tenant_id,
                    "node_type": node_data.get("node_type", "concept"),
                    "external_id": external_id,
                    "name": node_data.get("name", ""),
                    "description": node_data.get("description"),
                    "properties": node_data.get("properties", {}),
                    "created_at": now,
                    "updated_at": now,
                }
                created = await self._node_repo.create(create_data)
                result.nodes_created += 1
                node_id_map[external_id or str(node_data.get("id", ""))] = created.id

        for edge_data in data.edges:
            source_key = edge_data.get("source_node_id", "")
            target_key = edge_data.get("target_node_id", "")
            source_id = node_id_map.get(source_key, source_key)
            target_id = node_id_map.get(target_key, target_key)

            create_data: dict[str, Any] = {
                "tenant_id": tenant_id,
                "source_node_id": source_id,
                "target_node_id": target_id,
                "edge_type": edge_data.get("edge_type", "references"),
                "weight": edge_data.get("weight", 1.0),
                "properties": edge_data.get("properties", {}),
                "created_at": now,
            }
            await self._edge_repo.create(create_data)
            result.edges_created += 1

        return result

    async def export_ontology(
        self,
        tenant_id: str,
        params: OntologyExport,
    ) -> str:
        nodes = await self._node_repo.list_all_for_tenant(
            tenant_id=tenant_id,
            node_types=params.node_types,
        )
        edge_nodes = {n.id for n in nodes}

        all_edges = await self._edge_repo.list_all_for_tenant(tenant_id=tenant_id)
        edges = [
            e for e in all_edges
            if e.source_node_id in edge_nodes or e.target_node_id in edge_nodes
        ]

        payload = {
            "nodes": [
                {
                    "external_id": n.external_id,
                    "node_type": n.node_type,
                    "name": n.name,
                    "description": n.description,
                    "properties": n.properties,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "source_node_id": e.source_node_id,
                    "target_node_id": e.target_node_id,
                    "edge_type": e.edge_type,
                    "weight": e.weight,
                    "properties": e.properties,
                }
                for e in edges
            ],
        }

        import json

        if params.format == "yaml":
            return yaml.safe_dump(payload, default_flow_style=False, sort_keys=False)
        return json.dumps(payload, indent=2, default=str)

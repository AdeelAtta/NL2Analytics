from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from ke.api.schemas import (
    KEErrorCode,
    KEListResponse,
    KEResponse,
    error_response,
    success_response,
)
from ke.models.graph import GraphEdge as GraphEdgeModel
from ke.models.graph import GraphNode as GraphNodeModel
from ke.models.graph import GraphPath, OntologyExport, OntologyImport
from ke.services.ontology import OntologyService
from ke.stores.graph.repository import GraphEdgeRepository, GraphNodeRepository
from shared.models.pagination import PaginationParams

router = APIRouter(tags=["graph"])


async def _get_node_repo(session: AsyncSession = Depends(get_session)) -> GraphNodeRepository:
    return GraphNodeRepository(session)


async def _get_edge_repo(session: AsyncSession = Depends(get_session)) -> GraphEdgeRepository:
    return GraphEdgeRepository(session)


@router.get("/nodes", response_model=KEListResponse[GraphNodeModel])
async def list_nodes(
    request: Request,
    node_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    repo: GraphNodeRepository = Depends(_get_node_repo),
):
    pagination = PaginationParams(page=page, page_size=page_size)
    items, total = await repo.list(
        tenant_id=request.state.tenant_id,
        node_type=node_type,
        pagination=pagination,
    )
    return KEListResponse[GraphNodeModel](
        data=items,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)),
        },
    )


@router.get("/nodes/{node_id}", response_model=KEResponse[GraphNodeModel])
async def get_node(
    node_id: str,
    repo: GraphNodeRepository = Depends(_get_node_repo),
):
    node = await repo.get(node_id)
    if node is None:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": node_id})
    return success_response(node)


@router.post("/nodes", response_model=KEResponse[GraphNodeModel], status_code=201)
async def create_node(
    request: Request,
    payload: GraphNodeModel,
    repo: GraphNodeRepository = Depends(_get_node_repo),
):
    data = payload.model_dump(exclude={"id", "created_at", "updated_at"})
    data["tenant_id"] = request.state.tenant_id
    node = await repo.create(data)
    return success_response(node)


@router.put("/nodes/{node_id}", response_model=KEResponse[GraphNodeModel])
async def update_node(
    node_id: str,
    payload: GraphNodeModel,
    repo: GraphNodeRepository = Depends(_get_node_repo),
):
    data = payload.model_dump(exclude={"id", "tenant_id", "created_at", "updated_at"})
    node = await repo.update(node_id, data)
    if node is None:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": node_id})
    return success_response(node)


@router.delete("/nodes/{node_id}", response_model=KEResponse[None])
async def delete_node(
    node_id: str,
    repo: GraphNodeRepository = Depends(_get_node_repo),
):
    deleted = await repo.delete(node_id)
    if not deleted:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": node_id})
    return success_response(None)


@router.get("/edges", response_model=KEListResponse[GraphEdgeModel])
async def list_edges(
    request: Request,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
    edge_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    repo: GraphEdgeRepository = Depends(_get_edge_repo),
):
    pagination = PaginationParams(page=page, page_size=page_size)
    items, total = await repo.list(
        tenant_id=request.state.tenant_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        edge_type=edge_type,
        pagination=pagination,
    )
    return KEListResponse[GraphEdgeModel](
        data=items,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, -(-total // page_size)),
        },
    )


@router.get("/edges/{edge_id}", response_model=KEResponse[GraphEdgeModel])
async def get_edge(
    edge_id: str,
    repo: GraphEdgeRepository = Depends(_get_edge_repo),
):
    edge = await repo.get(edge_id)
    if edge is None:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": edge_id})
    return success_response(edge)


@router.post("/edges", response_model=KEResponse[GraphEdgeModel], status_code=201)
async def create_edge(
    request: Request,
    payload: GraphEdgeModel,
    repo: GraphEdgeRepository = Depends(_get_edge_repo),
):
    data = payload.model_dump(exclude={"id", "created_at"})
    data["tenant_id"] = request.state.tenant_id
    edge = await repo.create(data)
    return success_response(edge)


@router.put("/edges/{edge_id}", response_model=KEResponse[GraphEdgeModel])
async def update_edge(
    edge_id: str,
    payload: GraphEdgeModel,
    repo: GraphEdgeRepository = Depends(_get_edge_repo),
):
    data = payload.model_dump(exclude={"id", "tenant_id", "created_at"})
    edge = await repo.update(edge_id, data)
    if edge is None:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": edge_id})
    return success_response(edge)


@router.delete("/edges/{edge_id}", response_model=KEResponse[None])
async def delete_edge(
    edge_id: str,
    repo: GraphEdgeRepository = Depends(_get_edge_repo),
):
    deleted = await repo.delete(edge_id)
    if not deleted:
        return error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": edge_id})
    return success_response(None)


async def _get_ontology_service(
    node_repo: GraphNodeRepository = Depends(_get_node_repo),
    edge_repo: GraphEdgeRepository = Depends(_get_edge_repo),
) -> OntologyService:
    return OntologyService(node_repo=node_repo, edge_repo=edge_repo)


@router.post("/import", response_model=KEResponse[dict])
async def import_ontology(
    request: Request,
    payload: OntologyImport,
    service: OntologyService = Depends(_get_ontology_service),
):
    result = await service.import_ontology(
        tenant_id=request.state.tenant_id,
        data=payload,
    )
    return success_response({
        "nodes_created": result.nodes_created,
        "nodes_updated": result.nodes_updated,
        "edges_created": result.edges_created,
        "edges_updated": result.edges_updated,
    })


@router.post("/export", response_model=KEResponse[dict])
async def export_ontology(
    request: Request,
    payload: OntologyExport,
    service: OntologyService = Depends(_get_ontology_service),
):
    output = await service.export_ontology(
        tenant_id=request.state.tenant_id,
        params=payload,
    )
    return success_response({"format": payload.format, "data": output})


class TraverseParams(BaseModel):
    start_node_id: str
    end_node_id: str | None = None
    max_depth: int = 5
    edge_types: list[str] | None = None


@router.post("/traverse", response_model=KEListResponse[GraphPath])
async def traverse_graph(
    params: TraverseParams,
    repo: GraphEdgeRepository = Depends(_get_edge_repo),
):
    paths = await repo.traverse(
        start_node_id=params.start_node_id,
        end_node_id=params.end_node_id,
        max_depth=params.max_depth,
        edge_types=params.edge_types,
    )
    return KEListResponse[GraphPath](
        data=paths,
        meta={"total": len(paths)},
    )

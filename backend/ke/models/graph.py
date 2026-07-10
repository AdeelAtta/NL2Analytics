from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field

from shared.models.base import BaseSchema

UUIDStr = Annotated[
    str,
    BeforeValidator(lambda v: str(v) if not isinstance(v, str) else v),
]

NodeType = Literal[
    "table",
    "column",
    "domain",
    "concept",
    "glossary_term",
    "query_pattern",
]

EdgeType = Literal[
    "belongs_to",
    "references",
    "maps_to",
    "frequently_joined",
    "semantic_parent",
]


class GraphNode(BaseSchema):
    model_config = {"from_attributes": True}

    id: UUIDStr
    tenant_id: UUIDStr
    node_type: NodeType
    external_id: str | None = None
    name: str
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class GraphEdge(BaseSchema):
    model_config = {"from_attributes": True}

    id: UUIDStr
    tenant_id: UUIDStr
    source_node_id: UUIDStr
    target_node_id: UUIDStr
    edge_type: EdgeType
    weight: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class GraphPath(BaseSchema):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_weight: float = 0.0
    depth: int = 0


class OntologyImport(BaseSchema):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    mode: Literal["merge", "replace"] = "merge"


class OntologyExport(BaseSchema):
    tenant_id: UUIDStr
    node_types: list[NodeType] | None = None
    format: Literal["json", "yaml"] = "json"

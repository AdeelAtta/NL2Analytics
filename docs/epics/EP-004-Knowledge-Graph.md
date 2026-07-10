# EP-004: Knowledge Engine — Knowledge Graph

Epic ID: **EP-004** | Priority: **P1** | Dependencies: **EP-002** | Complexity: **Medium** | Agent: **Knowledge Engine Agent**

---

Implement the knowledge graph layer — a recursive CTE-driven graph stored in PostgreSQL that captures business ontology, table relationships, query patterns, and semantic connections.

## Goals
- Graph schema (nodes, edges, properties) in PostgreSQL
- Business ontology nodes (domains, concepts, glossaries)
- Query pattern graph (chains of tables joined in historical queries) 
- Recursive CTE traversal for path discovery
- Graph CRUD operations via KE API

## Out of Scope
- Graph visualization UI (EP-014)
- Automated relationship inference (EP-006)
- External graph DB (ADR-002 mandates PostgreSQL + recursive CTEs)

## Tasks

| ID | Name | P | Deps | Est | Status |
|----|------|---|---|-----|--------|
| TASK-023 | Design and create graph store data models | P0 | TASK-009 | M | ✅ Done |
| TASK-024 | Implement graph node CRUD repository | P0 | TASK-023 | L | ✅ Done |
| TASK-025 | Implement graph edge CRUD repository | P0 | TASK-023 | L | ✅ Done |
| TASK-026 | Implement recursive CTE traversal queries | P1 | TASK-024 | XL | ✅ Done |
| TASK-027 | Build ontology import/export service | P1 | TASK-024 | M | ✅ Done |
| TASK-028 | Write unit and integration tests | P0 | TASK-024 | L | ✅ Done |

## Key Design Decisions
- Graph stored as `graph_nodes` and `graph_edges` tables
- Node types: `table`, `column`, `domain`, `concept`, `glossary_term`, `query_pattern`
- Edge types: `belongs_to`, `references`, `maps_to`, `frequently_joined`, `semantic_parent`
- Traversal uses PostgreSQL `WITH RECURSIVE` CTEs
- Max traversal depth: 5 (configurable per tenant)

## Acceptance Criteria
- Can create, read, update, delete graph nodes and edges
- Recursive CTE traversal finds shortest path between any two nodes in < 200ms
- Ontology import from JSON/YAML works correctly
- Query pattern edges are lightweight (< 1KB per edge payload)
- Graph operations scale to 10K nodes per tenant

## Definition of Done
- Recursive CTE traversal benchmarked against 10K-node graph
- Integration tests cover all edge types
- Graph CRUD operations available through KE API

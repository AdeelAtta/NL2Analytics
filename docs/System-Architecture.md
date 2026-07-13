# System Architecture

## Overview

SchemaIntern is a DB-aware Natural Language to SQL platform. Users ask questions in plain English, and the system generates accurate, safe SQL queries against connected databases.

## Architecture Diagram

```
Browser ──► Nginx (port 8080, production)
                  │
          ┌───────┴───────┐
          ▼               ▼
     Frontend           Backend
   (Next.js 15)      (FastAPI :8100)
   Port 3000              │
          │               │
          └───────┬───────┘
                  ▼
             PostgreSQL 16
         (App data + test databases)
```

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| Database | PostgreSQL 16 (single instance) |
| Auth | JWT (python-jose), bcrypt, HTTP Bearer + API keys |
| AI/LLM | LangGraph, HuggingFace / OpenAI (configurable) |
| Infrastructure | Docker, Docker Compose |
| Observability | OpenTelemetry, Prometheus, Grafana (optional) |

## Services

| Service | Port | Description |
|---|---|---|
| Frontend | 3000 | Next.js application (App Router) |
| Backend API | 8100 | FastAPI — auth, query, schema sync, connections |
| PostgreSQL | 5432 | Database — app data + test datasets |
| Nginx | 8080 | Reverse proxy (production stack only) |

## Backend Modules

| Module | Path | Purpose |
|---|---|---|
| App API | `backend/app/` | External REST API — auth, query, connections, schema |
| Knowledge Engine | `backend/ke/` | NL2SQL pipeline, schema resolution, guardrails |
| Schema Intelligence | `backend/schema_intelligence/` | Database connectors, schema discovery, annotation |
| Shared | `backend/shared/` | Shared Pydantic models, pagination |

## Data Flow

```
1. User submits natural language query
2. Frontend sends to POST /api/v1/query
3. PipelineOrchestrator processes:
   a. IntentAgent classifies query
   b. SchemaResolver fetches table/column metadata from PostgreSQL
   c. Generator builds SQL via LLM (HuggingFace/OpenAI)
   d. GuardrailStack validates SQL (10-layer policy chain)
   e. Returns generated SQL + metadata to frontend
4. Result saved to query history
```

## Database Schema

PostgreSQL 16 with the following schemas:
- `public` — tenants, databases, schema_infos, tables, columns, relationships
- `schema_store` — DDL versioning
- `graph_store` — knowledge graph nodes and edges
- `query_store` — query history and feedback
- `audit` — audit log

## Test Databases

8 pre-seeded databases on first Docker startup (titanic, chinook, lego, netflix, pagila, dvdrental, periodic_table, happiness_index). Auto-seeded via `postgres-init` script.

## Deployment

### Dev Stack
```bash
docker compose -f docker-compose.dev.yml up --build
```
- Hot-reload frontend + backend
- PostgreSQL on port 5432
- Frontend at :3000, API at :8100

### Production Stack
```bash
docker compose up --build
```
- Nginx reverse proxy on port 8080
- No hot-reload, optimized builds
- Auto-migrations on startup

## Environment Files

| File | Used By | Tracked |
|---|---|---|
| `.env.dev` | Dev stack | Yes (safe defaults) |
| `.env.prod` | Production stack | No (secrets) |
| `.env.example` | Template | Yes |

## Removed Components (Historical)

| Component | Reason |
|---|---|
| Redis | Not required — session service degrades to in-memory |
| Qdrant | Not required — schema resolution uses PostgreSQL |
| Kubernetes / Helm | Deployment uses Docker Compose |
| Terraform | No cloud infrastructure provisioned |

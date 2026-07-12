# OpenQuery — Enterprise Data Intelligence Platform

AI-powered natural language querying for enterprise databases.

## Architecture

OpenQuery connects to enterprise databases (PostgreSQL, MySQL, Snowflake, BigQuery) and lets users ask questions in natural language. The platform:

1. **Discovers** schema meaning automatically (no manual YAML)
2. **Retrieves** relevant context from a self-learning Knowledge Engine
3. **Plans** optimal query strategies
4. **Generates** and validates SQL
5. **Enforces** enterprise security policies
6. **Executes** queries safely
7. **Learns** from feedback

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy |
| Frontend | Next.js 15, TypeScript, Tailwind, shadcn/ui |
| Database | PostgreSQL 16, Redis 7, Qdrant 1.12 |
| AI | LangGraph, vLLM/SGLang, SQLCoder |
| Infrastructure | Docker, K8s, Terraform, Helm |
| CI/CD | GitHub Actions, ArgoCD |
| Observability | OpenTelemetry, Prometheus, Grafana |

## Quick Start

### Option A: All-in-One Docker (recommended)

Starts everything — database, cache, backend & frontend — with hot-reload.

```bash
# Start all services
docker compose -f docker-compose.dev.yml up --build

# Background mode
docker compose -f docker-compose.dev.yml up --build -d

# Verify
curl http://localhost:8100/api/v1/health/live
open http://localhost:3000
```

Add your HuggingFace token to `.env.dev` for LLM-powered SQL generation:

```env
HF_TOKEN=hf_xxxxxxxxxx
```

Stop with `docker compose -f docker-compose.dev.yml down`.

### Option B: Native (manual)

#### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose
- uv (Python package manager): `pip install uv`

#### Setup

```bash
# Install dependencies
make install

# Set up environment
cp .env.example .env

# Start infrastructure services
docker compose -f infra/docker/docker-compose.db.yml up -d

# Run database migrations
make db-migrate

# Start development servers
make dev
```

#### Verify

```bash
# Backend health
curl http://localhost:8100/api/v1/health/live

# Frontend
open http://localhost:3000
```

### Docker Dev Services

| Service | Port | Hot-Reload |
|---|---|---|
| `postgres` | 5432 | — |
| `redis` | 6379 | — |
| `qdrant` | 6333 / 6334 | — |
| `backend` | 8100 | ✅ uvicorn `--reload` + bind mount |
| `frontend` | 3000 | ✅ Next.js Turbopack HMR + bind mount |

## Project Structure

```
openquery/
├── backend/            # Python FastAPI services
│   ├── public-api/     # External API (port 8100)
│   ├── ke-api/         # Knowledge Engine API (port 8200)
│   ├── query-pipeline/ # NL2SQL agent pipeline
│   ├── schema-intel/   # Schema intelligence workers
│   ├── learning-loop/  # Self-learning workers
│   ├── auth/           # Authentication service
│   └── lib/            # Shared Python libraries
├── frontend/           # Next.js application
├── infra/              # Infrastructure
│   ├── docker/         # Dockerfiles and Compose
│   ├── k8s/            # Kubernetes manifests
│   ├── terraform/      # Terraform modules
│   └── helm/           # Helm charts
├── shared/             # Shared type definitions
└── docs/               # Documentation
```

## Development

See [Development Guide](docs/development-guide.md) for detailed setup instructions.

## Documentation

All documentation is in `/docs/`. Key documents:

- [Architecture Overview](docs/System-Architecture.md)
- [API Specification](docs/specifications/API-Specification.md)
- [Database Specification](docs/specifications/Database-Specification.md)
- [Engineering Standards](docs/specifications/Engineering-Standards.md)
- [Implementation Plan](docs/Implementation-Plan.md)

## License

Proprietary — All Rights Reserved

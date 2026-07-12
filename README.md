# SchemaIntern — DB-Aware NL to SQL

Schema-aware natural language to SQL — knows your database schema and generates accurate, safe SQL queries.

## Architecture

SchemaIntern connects to enterprise databases (PostgreSQL, MySQL, Snowflake, BigQuery) and lets users ask questions in natural language. The platform:

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

### Seed Data

On first startup, PostgreSQL is automatically seeded with two test databases:

| Database | Schema | Rows |
|---|---|---|
| `titanic` | `passenger` | 30 passengers |
| `employees` | `departments`, `employees`, `dept_emp`, `titles`, `salaries` | 10 employees |

Connect to these from the web UI via **Settings → Connections → Add Connection**:

| Field | Value (Docker) | Value (Native) |
|---|---|---|
| Host | `host.docker.internal` | `localhost` |
| Port | `5432` | `5432` |
| Database | `titanic` or `employees` | `titanic` or `employees` |
| User | `postgres` | `postgres` |
| Password | `postgres` | `postgres` |

Then try queries like `"how many male passengers?"` or `"list all employees in Sales"`.

> **Docker tip**: Use `host.docker.internal` as the host — it resolves to your host machine from inside the container. The UI will also show this hint when the host field is set to `localhost`.

### Adding More Databases

Additional SQL dumps are available in `test-databases/`:

| File | Database name |
|---|---|
| `lego.sql` | `lego` |
| `chinook.sql` | `chinook` |
| `netflix.sql` | `netflix` |
| `pagila.sql` | `pagila` |
| `dvdrental.sql` | `dvdrental` |
| `periodic_table.sql` | `periodic_table` |
| `happiness_index.sql` | `happiness_index` |

Seed any of them on demand:

```bash
# Seed a single database
make seed DB=lego

# Seed everything
make seed-all

# If running Docker (not needed when using docker-compose.dev.yml):
make seed-docker DB=chinook
```

The script auto-detects your local PostgreSQL or Docker environment.

### Docker Dev Services

| Service | Port | Hot-Reload |
|---|---|---|
| `postgres` | 5432 | — (auto-seeded on first run) |
| `redis` | 6379 | — |
| `qdrant` | 6333 / 6334 | — |
| `backend` | 8100 | ✅ uvicorn `--reload` + bind mount |
| `frontend` | 3000 | ✅ Next.js Turbopack HMR + bind mount |

## Workflow Commands

| Command | Description |
|---|---|
| `make install` | Install all dependencies (backend + frontend) |
| `make dev` | Start native dev servers (backend :8100, frontend :3000) |
| `make test` | Run all tests |
| `make test-backend` | Run backend tests only |
| `make test-frontend` | Run frontend tests only |
| `make lint` | Run all linters |
| `make typecheck` | Run type checkers (mypy + tsc) |
| `make format` | Format all code |
| `make build-backend` | Build backend Docker image |
| `make build-frontend` | Build frontend Docker image |
| `make db-migrate` | Run database migrations |
| `make db-seed` | Seed placeholder data (legacy) |
| `make seed DB=lego PASSWORD=123` | Seed a test database |
| `make seed-all PASSWORD=123` | Seed all test databases |
| `make seed-docker DB=chinook` | Seed using Docker PostgreSQL |
| `make clean` | Clean build artifacts |

### Docker

| Command | Description |
|---|---|
| `docker compose -f docker-compose.dev.yml up --build` | Start everything with hot-reload |
| `docker compose -f docker-compose.dev.yml up --build -d` | Start in background |
| `docker compose -f docker-compose.dev.yml down` | Stop all services |
| `docker compose -f docker-compose.dev.yml logs -f backend` | Tail backend logs |
| `docker compose -f infra/docker/docker-compose.db.yml up -d` | Start only infra (PG, Redis, Qdrant) |

### Manual seeds (without Make)

```bash
# List available databases
./bin/seed.sh

# Seed one database
POSTGRES_PASSWORD=123 ./bin/seed.sh lego

# Seed all databases
POSTGRES_PASSWORD=123 ./bin/seed.sh --all

# Target Docker PostgreSQL
./bin/seed.sh --docker lego
```

## Project Structure

```
schemaintern/
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

# Agent: Infrastructure

| Metadata | Value |
|----------|-------|
| **Agent ID** | AGENT-INFRA |
| **Owns Epics** | EP-001, EP-015, EP-016 |
| **Workspace** | `/infra/`, `/.github/`, `/scripts/`, root config files |
| **Reads** | `/docs/Implementation-Plan.md`, `/docs/epics/EP-001`, EP-015, EP-016 |

---

## Responsibilities

1. Initialize and maintain the monorepo structure with Python and Node.js workspaces
2. Configure all developer tooling (Python uv/ruff/mypy/pytest, Node.js/Next, pre-commit)
3. Create Dockerfiles for all services
4. Create Kubernetes manifests + Helm charts for all deployment modes (K8s/Helm/Terraform removed — uses Docker Compose)
5. Create Terraform modules for cloud-agnostic IaC (removed)
6. Implement CI/CD pipelines (GitHub Actions)
7. Set up monitoring, logging, error tracking, alerting
8. Configure secret management and feature flags
9. Maintain root config files (pyproject.toml, Makefile, .env.example, .gitignore)
10. Create Docker Compose for local development

## Workspace Boundaries

```
/                           -> Makefile, pyproject.toml, package.json, README.md, .gitignore, .pre-commit-config.yaml
/infra/                     -> All infrastructure code
  /docker/                  -> Dockerfiles (K8s, Terraform, Helm removed)
/.github/                   -> CI/CD workflows and actions
/scripts/                   -> Utility scripts
```

## DO NOT Touch

- `/backend/` (any backend application code)
- `/frontend/` (any frontend application code)
- `/research/` (research experiments)
- `/docs/tasks/` except to update task status

## Prompts

### Initial Setup Prompt
```
You are the Infrastructure Agent for the Enterprise Data Intelligence Platform.
Your job is to set up the development environment, CI/CD, and Docker (K8s and Terraform removed).

Start with EP-001 (Dev Environment):
1. Initialize the monorepo with /backend/ and /frontend/ workspace
2. Create pyproject.toml for Python (uv-based)
3. Create package.json for frontend
4. Create Makefile with: install, dev, test, lint, typecheck, build
5. Create .pre-commit-config.yaml with ruff and mypy hooks
6. Create Dockerfile for each service
7. Create docker-compose.yml with PostgreSQL (Redis and Qdrant were removed)
8. Create .env.example with all configuration variables

Then proceed to EP-015 and EP-016.
```

### CI Task Prompt
```
Implement CI pipeline:
1. Create .github/workflows/ci.yml
   - Trigger: push and PR to main
   - Jobs: lint -> typecheck -> unit-test -> integration-test -> build
   - Caching for pip/npm dependencies
2. Create .github/workflows/cd.yml
   - Trigger: push to main (after CI passes)
   - Jobs: build images -> push registry -> deploy dev

Read EP-016 for full details.
```

## Definition of Done
- All assigned tasks are marked `done` in their respective task files
- No files outside `/infra/`, `/.github/`, `/scripts/`, or root config were modified
- All acceptance criteria for assigned epics are met
- Task status files were updated

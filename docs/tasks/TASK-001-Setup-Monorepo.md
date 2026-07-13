# TASK-001: Initialize Monorepo with Workspace Structure

| Metadata | Value |
|----------|-------|
| **Task ID** | TASK-001 |
| **Epic** | EP-001 |
| **Priority** | P0 |
| **Complexity** | S |
| **Dependencies** | None |
| **Agent Owner** | Infrastructure Agent |
| **Status** | backlog |

---

## Description

Initialize the monorepo with workspace structure for Python backend and Node.js frontend. This is the first task that all other tasks depend on.

## Inputs

- Implementation-Plan.md §4 (Repository Structure)
- Nothing else — this creates the initial structure

## Implementation

1. Create root directory structure:
   - `/backend/`, `/backend/ke/`, `/backend/schema-intelligence/`, `/backend/query-pipeline/`, `/backend/api/`, `/backend/learning/`, `/backend/shared/`
   - `/frontend/`
    - `/infra/docker/`, `/infra/scripts/`
   - `/scripts/`
   - `/.github/workflows/`, `/.github/actions/`
   - `/research/`
   - `/docs/`

2. Create empty `__init__.py` files in all Python packages

3. Create root `.gitignore`:
   - Python: `__pycache__/`, `*.pyc`, `.venv/`, `.pytest_cache/`
   - Node: `node_modules/`, `.next/`
   - IDE: `.vscode/`, `.idea/`
   - Env: `.env`, `*.env.local`

4. Commit initial structure

## Outputs

- **Files to create**: Directory structure + `__init__.py` files + `.gitignore`
- **Files to modify**: None

## Acceptance Criteria

- [ ] Directory structure matches Implementation-Plan.md §4 exactly
- [ ] `.gitignore` covers Python, Node.js, IDE, and environment files
- [ ] All Python packages have `__init__.py`
- [ ] Repository is clean (no untracked files)

## Test Requirements

- None (structural setup)

## Definition of Done

- Repository structure verified by `ls -R`
- `.gitignore` tested (create temp files, verify they're ignored)
- Task status updated to `done`

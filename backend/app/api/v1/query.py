from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.dependencies import get_current_user
from ke.models.pipeline import PipelineResult
from ke.services.pipeline import PipelineOrchestrator

router = APIRouter(prefix="/api/v1/query", tags=["query"])

_orchestrator: PipelineOrchestrator | None = None


def _get_orchestrator() -> PipelineOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = PipelineOrchestrator()
    return _orchestrator


@router.post("")
async def execute_query(
    request: Request,
    body: dict[str, Any],
    current_user: dict[str, str] = Depends(get_current_user),
    orchestrator: PipelineOrchestrator = Depends(_get_orchestrator),
) -> dict[str, Any]:
    if current_user.get("sub") == "anonymous":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Query is required",
        )

    tenant_id = getattr(request.state, "tenant_id", current_user.get("sub", "default"))
    session_id = body.get("session_id")
    dry_run = body.get("dry_run", True)

    result: PipelineResult = await orchestrator.execute(
        tenant_id=tenant_id,
        query=query,
        session_id=session_id,
        dry_run=dry_run,
    )

    resp = _pipeline_to_response(result)
    from ke.services.explain import explain_sql, extract_columns
    resp["explanation"] = explain_sql(result.sql or "", result.query)
    resp["columns"] = extract_columns(result.sql or "")
    return resp


def _pipeline_to_response(result: PipelineResult) -> dict[str, Any]:
    return {
        "success": result.status.value == "success",
        "query": result.query,
        "sql": result.sql or "",
        "status": result.status.value,
        "error": result.error,
        "stages": [
            {
                "name": s.name,
                "status": s.status,
                "duration_ms": s.duration_ms,
                "error": s.error,
            }
            for s in result.stages
        ],
        "total_duration_ms": result.total_duration_ms,
        "session_id": result.session_id,
        "quality_score": result.quality_score.model_dump() if result.quality_score else None,
    }

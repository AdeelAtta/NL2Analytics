from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth.dependencies import get_current_user
from app.core.database import get_session
from ke.models.pipeline import PipelineResult
from ke.services.pipeline import PipelineOrchestrator
from ke.services.history import QueryHistoryService
from ke.stores.query.repository import QueryHistoryRepository, QueryFeedbackRepository

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

    tenant_id = getattr(request.state, "tenant_id", current_user.get("tenant_id", "demo"))

    if body.get("dry_run") == "preview":
        from ke.services.schema_registry import get_schema
        from ke.services.intent import IntentAgent
        from ke.services.prompts import format_schema_ddl
        schema_data = get_schema(tenant_id)
        if not schema_data:
            return {"success": False, "error": "No schema synced for this tenant. Sync a database first."}
        intent = IntentAgent().classify(query, schema_data)
        ddl = format_schema_ddl(schema_data.get("tables",[]), schema_data.get("columns",[]), schema_data.get("relationships",[]))
        return {"success": True, "preview": True, "schema": ddl, "tables": [t.name for t in intent.tables]}

    session_id = body.get("session_id")
    dry_run = body.get("dry_run", True)

    result: PipelineResult = await orchestrator.execute(
        tenant_id=tenant_id,
        query=query,
        session_id=session_id,
        dry_run=dry_run,
    )

    # Save to query history
    try:
        async with get_session() as session:
            history_svc = QueryHistoryService(
                history_repo=QueryHistoryRepository(session),
                feedback_repo=QueryFeedbackRepository(session),
            )
            await history_svc.save(
                tenant_id=tenant_id,
                user_id=current_user.get("sub", ""),
                query=query,
                sql=result.sql or "",
                status=result.status.value,
                duration_ms=result.total_duration_ms,
                model_tier=result.model_tier,
                model_name=result.model_name,
                guard_passed=result.guard_passed,
                guard_stopped_at=result.guard_stopped_at,
                stage_data=[s.model_dump() for s in result.stages],
            )
    except Exception:
        import logging
        logging.exception("Failed to save query history")

    resp = _pipeline_to_response(result)
    from ke.services.explain import explain_sql, extract_columns
    resp["explanation"] = explain_sql(result.sql or "", result.query)
    resp["columns"] = extract_columns(result.sql or "", tenant_id)
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
        "model_tier": result.model_tier,
        "model_name": result.model_name,
        "total_duration_ms": result.total_duration_ms,
        "session_id": result.session_id,
        "quality_score": result.quality_score.model_dump() if result.quality_score else None,
    }

from __future__ import annotations

import time
import uuid
from typing import Any

from opentelemetry import trace

from ke.models.execution import ExecutionResult
from ke.models.generation import GenerationResult, GenerationStatus
from ke.models.pipeline import PipelineResult, PipelineStageResult, PipelineStatus
from ke.models.planning import QueryIntent, QueryPlan, QueryType
from ke.models.policy import PolicyChainResult
from ke.services.executor import QueryExecutor
from ke.services.generator import NL2SQLGenerator
from ke.services.intent import IntentAgent
from ke.services.planner import QueryPlanner
from ke.services.policy.chain import PolicyChain
from ke.services.quality_scorer import QueryQualityScorer
from ke.services.schema_resolver import SchemaResolver
from ke.services.session import InMemorySessionService

_tracer = trace.get_tracer("ke.pipeline")

try:
    from app.core.metrics import (
        record_pipeline_result,
        record_stage_result,
        record_query_type,
        record_guard_blocked,
    )
except ImportError:
    def record_pipeline_result(*args: Any, **kwargs: Any) -> None: ...
    def record_stage_result(*args: Any, **kwargs: Any) -> None: ...
    def record_query_type(*args: Any, **kwargs: Any) -> None: ...
    def record_guard_blocked(*args: Any, **kwargs: Any) -> None: ...


def _set_stage_span_attrs(
    span: trace.Span,
    name: str,
    status: str,
    duration_ms: float,
) -> None:
    span.set_attribute("stage.name", name)
    span.set_attribute("stage.status", status)
    span.set_attribute("stage.duration_ms", duration_ms)


class PipelineOrchestrator:
    def __init__(
        self,
        intent_agent: IntentAgent | None = None,
        planner: QueryPlanner | None = None,
        generator: NL2SQLGenerator | None = None,
        policy_chain: PolicyChain | None = None,
        executor: QueryExecutor | None = None,
        quality_scorer: QueryQualityScorer | None = None,
    ) -> None:
        self._intent_agent = intent_agent or IntentAgent()
        self._planner = planner or QueryPlanner(intent_agent=self._intent_agent)
        self._generator = generator or NL2SQLGenerator()
        self._policy_chain = policy_chain or PolicyChain()
        self._executor = executor or QueryExecutor()
        self._quality_scorer = quality_scorer

    async def execute(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        schema_resolver: SchemaResolver | None = None,
        session_service: InMemorySessionService | None = None,
        session_id: str | None = None,
        tenant_id: str = "default",
        tenant_tier: str = "pro",
        num_candidates: int = 1,
        reflect: bool = True,
        timeout: float = 30.0,
        page: int = 1,
        page_size: int = 1000,
        dry_run: bool = False,
        enable_quality: bool = True,
    ) -> PipelineResult:
        with _tracer.start_as_current_span("pipeline.execute") as root_span:
            root_span.set_attribute("query", query)
            root_span.set_attribute("tenant_id", tenant_id)
            root_span.set_attribute("tenant_tier", tenant_tier)

            result = await self._execute_inner(
                query, context, schema_resolver, session_service,
                session_id, tenant_id, tenant_tier,
                num_candidates, reflect, timeout, page, page_size, dry_run,
                enable_quality, root_span,
            )

            root_span.set_attribute("pipeline.status", result.status.value)
            root_span.set_attribute("pipeline.total_duration_ms", result.total_duration_ms)
            record_pipeline_result(result.status.value, result.total_duration_ms)
            return result

    async def _execute_inner(
        self,
        query: str,
        context: dict[str, Any] | None,
        schema_resolver: SchemaResolver | None,
        session_service: InMemorySessionService | None,
        session_id: str | None,
        tenant_id: str,
        tenant_tier: str,
        num_candidates: int,
        reflect: bool,
        timeout: float,
        page: int,
        page_size: int,
        dry_run: bool,
        enable_quality: bool,
        root_span: trace.Span,
    ) -> PipelineResult:
        pipeline_id = str(uuid.uuid4())
        start = time.perf_counter()
        stages: list[PipelineStageResult] = []
        merged_context = dict(context or {})

        if not merged_context.get("tables"):
            from ke.services.schema_registry import get_schema, build_ddl
            real = get_schema(tenant_id)
            if real and real.get("tables"):
                merged_context.setdefault("tables", real["tables"])
                merged_context.setdefault("columns", real["columns"])
                merged_context.setdefault("relationships", real.get("relationships", []))
                merged_context.setdefault("ddl_context",
                    build_ddl(real["tables"], real["columns"], real.get("relationships", [])))
            else:
                from app.core.config import get_settings
                if get_settings().environment != "production":
                    from ke.services.demo_data import get_demo_context
                    demo = get_demo_context()
                    merged_context.setdefault("tables", demo["tables"])
                    merged_context.setdefault("columns", demo["columns"])
                    merged_context.setdefault("relationships", demo["relationships"])
                    merged_context.setdefault("ddl_context", demo["ddl_context"])

        session_turns: list[Any] = []
        resolved_session_id = session_id or ""
        if session_service is not None:
            resolved_session_id, session_turns = await session_service.get_or_create(session_id, tenant_id)
            history_str = session_service.format_history(session_turns)
            if history_str:
                merged_context["conversation_history"] = history_str

        intent: QueryIntent | None = None
        plan: QueryPlan | None = None
        generation: GenerationResult | None = None
        quality_score = None
        guard_result: PolicyChainResult | None = None
        execution: ExecutionResult | None = None

        # Stage 1: Classify
        st = time.perf_counter()
        try:
            with _tracer.start_as_current_span("stage.classify") as stage_span:
                intent = self._intent_agent.classify(query, merged_context)
                elapsed = (time.perf_counter() - st) * 1000
                stage_status = "success"
                stages.append(PipelineStageResult(
                    name="classify",
                    status=stage_status,
                    data={"query_type": intent.query_type.value, "complexity": intent.complexity.value if hasattr(intent, "complexity") else "unknown"},
                    duration_ms=elapsed,
                ))
                stage_span.set_attribute("query_type", intent.query_type.value)
                _set_stage_span_attrs(stage_span, "classify", stage_status, elapsed)
                record_stage_result("classify", stage_status, elapsed)
                root_span.set_attribute("query_type", intent.query_type.value)
        except Exception as e:
            elapsed = (time.perf_counter() - st) * 1000
            stages.append(PipelineStageResult(name="classify", status="failed", error=str(e), duration_ms=elapsed))
            record_stage_result("classify", "failed", elapsed)
            return self._fail(pipeline_id, query, start, stages, str(e))

        if intent.query_type == QueryType.DDL:
            elapsed = (time.perf_counter() - start) * 1000
            stages.append(PipelineStageResult(name="plan", status="skipped"))
            stages.append(PipelineStageResult(name="generate", status="skipped"))
            stages.append(PipelineStageResult(name="guard", status="skipped"))
            stages.append(PipelineStageResult(name="execute", status="skipped"))
            record_query_type("DDL", "failed")
            return PipelineResult(id=pipeline_id, query=query, status=PipelineStatus.FAILED, stages=stages, total_duration_ms=elapsed, error="DDL operations are not supported")

        if intent.query_type == QueryType.UNKNOWN:
            elapsed = (time.perf_counter() - start) * 1000
            stages.append(PipelineStageResult(name="plan", status="skipped"))
            stages.append(PipelineStageResult(name="generate", status="skipped"))
            stages.append(PipelineStageResult(name="guard", status="skipped"))
            stages.append(PipelineStageResult(name="execute", status="skipped"))
            record_query_type("UNKNOWN", "failed")
            return PipelineResult(id=pipeline_id, query=query, status=PipelineStatus.FAILED, stages=stages, total_duration_ms=elapsed, error="Could not determine query intent")

        record_query_type(intent.query_type.value, "classified")

        # Schema resolution: enrich context with schema info based on classified intent
        if schema_resolver is not None:
            st = time.perf_counter()
            try:
                with _tracer.start_as_current_span("stage.resolve_schema") as stage_span:
                    schema_ctx = await schema_resolver.resolve(intent, tenant_id, query)
                    if schema_ctx.get("tables"):
                        merged_context.setdefault("tables", []).extend(schema_ctx["tables"])
                    if schema_ctx.get("columns"):
                        merged_context.setdefault("columns", []).extend(schema_ctx["columns"])
                    if schema_ctx.get("relationships"):
                        merged_context.setdefault("relationships", []).extend(schema_ctx["relationships"])
                    if schema_ctx.get("ddl_context"):
                        merged_context["ddl_context"] = schema_ctx["ddl_context"]
                    elapsed = (time.perf_counter() - st) * 1000
                    stage_status = "success"
                    stages.append(PipelineStageResult(
                        name="resolve_schema",
                        status=stage_status,
                        data={"tables_found": len(schema_ctx.get("tables", [])), "columns_found": len(schema_ctx.get("columns", []))},
                        duration_ms=elapsed,
                    ))
                    _set_stage_span_attrs(stage_span, "resolve_schema", stage_status, elapsed)
                    record_stage_result("resolve_schema", stage_status, elapsed)
            except Exception as e:
                elapsed = (time.perf_counter() - st) * 1000
                stages.append(PipelineStageResult(name="resolve_schema", status="failed", error=str(e), duration_ms=elapsed))
                record_stage_result("resolve_schema", "failed", elapsed)

        # Stage 2: Plan
        st = time.perf_counter()
        try:
            with _tracer.start_as_current_span("stage.plan") as stage_span:
                plan = await self._planner.plan(query, context=intent.model_dump(), intent=intent)
                elapsed = (time.perf_counter() - st) * 1000
                stage_status = "success"
                stages.append(PipelineStageResult(
                    name="plan",
                    status=stage_status,
                    data={"steps": len(plan.steps), "valid": plan.validation.valid},
                    duration_ms=elapsed,
                ))
                stage_span.set_attribute("plan.steps", len(plan.steps))
                stage_span.set_attribute("plan.valid", plan.validation.valid)
                _set_stage_span_attrs(stage_span, "plan", stage_status, elapsed)
                record_stage_result("plan", stage_status, elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - st) * 1000
            stages.append(PipelineStageResult(name="plan", status="failed", error=str(e), duration_ms=elapsed))
            record_stage_result("plan", "failed", elapsed)
            return self._fail(pipeline_id, query, start, stages, str(e))

        if plan.validation and not plan.validation.valid:
            fatal_errors = [e for e in plan.validation.errors if e.severity.value == "FATAL"]
            if fatal_errors:
                elapsed = (time.perf_counter() - start) * 1000
                stages.append(PipelineStageResult(name="generate", status="skipped"))
                stages.append(PipelineStageResult(name="guard", status="skipped"))
                stages.append(PipelineStageResult(name="execute", status="skipped"))
                return PipelineResult(
                    id=pipeline_id, query=query, status=PipelineStatus.FAILED, stages=stages,
                    total_duration_ms=elapsed, error=f"Plan validation failed: {fatal_errors[0].message}",
                )

        # Stage 3: Generate
        st = time.perf_counter()
        try:
            with _tracer.start_as_current_span("stage.generate") as stage_span:
                generation = await self._generator.generate(
                    query=query,
                    intent=intent,
                    context=merged_context,
                    tenant_tier=tenant_tier,
                    num_candidates=num_candidates,
                    reflect=reflect,
                )
                elapsed = (time.perf_counter() - st) * 1000
                stage_status = "success" if generation.status == GenerationStatus.COMPLETED else "failed"
                stages.append(PipelineStageResult(
                    name="generate",
                    status=stage_status,
                    data={"sql": generation.sql, "model_tier": generation.model_tier, "model_name": generation.model_name},
                    duration_ms=elapsed,
                ))
                stage_span.set_attribute("generation.status", generation.status.value)
                stage_span.set_attribute("generation.model_tier", generation.model_tier)
                stage_span.set_attribute("generation.model_name", generation.model_name)
                _set_stage_span_attrs(stage_span, "generate", stage_status, elapsed)
                record_stage_result("generate", stage_status, elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - st) * 1000
            stages.append(PipelineStageResult(name="generate", status="failed", error=str(e), duration_ms=elapsed))
            record_stage_result("generate", "failed", elapsed)
            return self._fail(pipeline_id, query, start, stages, str(e))

        if generation.status == GenerationStatus.FAILED:
            elapsed = (time.perf_counter() - start) * 1000
            stages.append(PipelineStageResult(name="guard", status="skipped"))
            stages.append(PipelineStageResult(name="execute", status="skipped"))
            return PipelineResult(
                id=pipeline_id, query=query, status=PipelineStatus.FAILED, stages=stages,
                total_duration_ms=elapsed,
                model_tier=generation.model_tier, model_name=generation.model_name,
                error=generation.error or "SQL generation failed",
            )

        # Stage 3b: Quality scoring (non-blocking, after generate, before guard)
        if enable_quality and self._quality_scorer is not None and generation and generation.sql:
            st = time.perf_counter()
            try:
                with _tracer.start_as_current_span("stage.quality") as stage_span:
                    quality_score = await self._quality_scorer.score(
                        sql=generation.sql,
                        query=query,
                        intent=intent,
                        context=merged_context,
                    )
                    elapsed = (time.perf_counter() - st) * 1000
                    stages.append(PipelineStageResult(
                        name="quality",
                        status="success",
                        data={"overall": quality_score.overall, "model": quality_score.model},
                        duration_ms=elapsed,
                    ))
                    stage_span.set_attribute("quality.overall", quality_score.overall)
                    stage_span.set_attribute("quality.model", quality_score.model)
                    _set_stage_span_attrs(stage_span, "quality", "success", elapsed)
                    record_stage_result("quality", "success", elapsed)
            except Exception as e:
                elapsed = (time.perf_counter() - st) * 1000
                stages.append(PipelineStageResult(name="quality", status="failed", error=str(e), duration_ms=elapsed))
                record_stage_result("quality", "failed", elapsed)

        # Stage 4: Guard
        st = time.perf_counter()
        try:
            with _tracer.start_as_current_span("stage.guard") as stage_span:
                guard_result = await self._policy_chain.enforce(generation.sql, merged_context)
                elapsed = (time.perf_counter() - st) * 1000
                stage_status = "blocked" if not guard_result.passed else "success"
                stages.append(PipelineStageResult(
                    name="guard",
                    status=stage_status,
                    data={"passed": guard_result.passed, "layers": len(guard_result.layers), "stopped_at": guard_result.stopped_at},
                    duration_ms=elapsed,
                ))
                stage_span.set_attribute("guard.passed", guard_result.passed)
                stage_span.set_attribute("guard.layers", len(guard_result.layers))
                stage_span.set_attribute("guard.stopped_at", guard_result.stopped_at or "")
                _set_stage_span_attrs(stage_span, "guard", stage_status, elapsed)
                record_stage_result("guard", stage_status, elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - st) * 1000
            stages.append(PipelineStageResult(name="guard", status="failed", error=str(e), duration_ms=elapsed))
            record_stage_result("guard", "failed", elapsed)
            return self._fail(pipeline_id, query, start, stages, str(e))

        if not guard_result.passed:
            elapsed = (time.perf_counter() - start) * 1000
            stages.append(PipelineStageResult(name="execute", status="skipped"))
            blocked_layer = next((l for l in guard_result.layers if l.blocked), None)
            layer_name = blocked_layer.layer_name if blocked_layer else guard_result.stopped_at
            record_guard_blocked(layer_name or "unknown")
            return PipelineResult(
                id=pipeline_id, query=query, status=PipelineStatus.BLOCKED, stages=stages,
                total_duration_ms=elapsed,
                sql=generation.sql if generation else "",
                model_tier=generation.model_tier if generation else "none",
                model_name=generation.model_name if generation else "",
                guard_passed=False,
                guard_stopped_at=guard_result.stopped_at,
                session_id=resolved_session_id,
                quality_score=quality_score,
                error=f"Blocked by guardrail: {layer_name}",
            )

        # Stage 5: Execute
        st = time.perf_counter()
        sql_to_execute = guard_result.sanitized_sql or generation.sql
        try:
            with _tracer.start_as_current_span("stage.execute") as stage_span:
                execution = await self._executor.execute(
                    sql=sql_to_execute,
                    timeout=timeout,
                    page=page,
                    page_size=page_size,
                    dry_run=dry_run,
                )
                elapsed = (time.perf_counter() - st) * 1000
                stage_status = execution.status.value
                stages.append(PipelineStageResult(
                    name="execute",
                    status=stage_status,
                    data={"row_count": execution.row_count, "total_rows": execution.total_rows, "truncated": execution.truncated},
                    duration_ms=elapsed,
                ))
                stage_span.set_attribute("execution.status", execution.status.value)
                stage_span.set_attribute("execution.row_count", execution.row_count)
                stage_span.set_attribute("execution.total_rows", execution.total_rows)
                stage_span.set_attribute("execution.dry_run", dry_run)
                _set_stage_span_attrs(stage_span, "execute", stage_status, elapsed)
                record_stage_result("execute", stage_status, elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - st) * 1000
            stages.append(PipelineStageResult(name="execute", status="failed", error=str(e), duration_ms=elapsed))
            record_stage_result("execute", "failed", elapsed)
            return self._fail(pipeline_id, query, start, stages, str(e))

        # Save turn to session
        if session_service is not None and resolved_session_id:
            await session_service.add_turn(
                session_id=resolved_session_id,
                query=query,
                sql=generation.sql if generation else "",
                result_summary=f"{execution.row_count} rows returned" if execution and execution.row_count else "",
                intent_type=intent.query_type.value if intent else "",
                model_tier=generation.model_tier if generation else "none",
                model_name=generation.model_name if generation else "",
            )

        overall_status = PipelineStatus.SUCCESS if execution.status.value in ("success", "dry_run") else PipelineStatus.FAILED
        return PipelineResult(
            id=pipeline_id,
            query=query,
            status=overall_status,
            stages=stages,
            total_duration_ms=(time.perf_counter() - start) * 1000,
            sql=generation.sql if generation else "",
            model_tier=generation.model_tier if generation else "none",
            model_name=generation.model_name if generation else "",
            guard_passed=guard_result.passed if guard_result else True,
            guard_stopped_at=guard_result.stopped_at if guard_result else None,
            session_id=resolved_session_id,
            quality_score=quality_score,
        )

    @staticmethod
    def _fail(
        pipeline_id: str,
        query: str,
        start: float,
        stages: list[PipelineStageResult],
        error: str,
    ) -> PipelineResult:
        return PipelineResult(
            id=pipeline_id, query=query, status=PipelineStatus.FAILED,
            stages=stages,
            total_duration_ms=(time.perf_counter() - start) * 1000,
            error=error,
        )

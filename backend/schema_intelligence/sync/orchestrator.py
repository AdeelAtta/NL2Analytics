from __future__ import annotations

import logging
from typing import Any

from schema_intelligence.annotators.base import BaseAnnotator
from schema_intelligence.annotators.rule_based import RuleBasedAnnotator
from schema_intelligence.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorRegistry,
    ExtractedSchemaInfo,
    ExtractedTable,
)
from schema_intelligence.inference.base import InferredRelationship
from schema_intelligence.inference.engine import RelationshipInferenceService
from schema_intelligence.parsers.ddl_parser import DDLParser
from schema_intelligence.services.annotation import AnnotationService
from schema_intelligence.sync.models import (
    SyncChange,
    SyncChangeType,
    SyncResult,
    SyncState,
    table_signature,
)

logger = logging.getLogger(__name__)


class SyncOrchestrator:
    def __init__(
        self,
        ddl_parser: DDLParser | None = None,
        annotation_service: AnnotationService | None = None,
        inference_service: RelationshipInferenceService | None = None,
        sync_state: SyncState | None = None,
    ) -> None:
        self._ddl_parser = ddl_parser
        self._annotation_service = annotation_service or AnnotationService(
            annotator=RuleBasedAnnotator()
        )
        self._inference_service = inference_service or RelationshipInferenceService()
        self._sync_state = sync_state or SyncState()

    @property
    def state(self) -> SyncState:
        return self._sync_state

    @state.setter
    def state(self, sync_state: SyncState) -> None:
        self._sync_state = sync_state

    def reset_state(self) -> None:
        self._sync_state = SyncState()

    async def sync(
        self,
        config: ConnectorConfig,
        db_type: str = "postgresql",
        schemas: list[str] | None = None,
        run_annotation: bool = True,
        run_inference: bool = True,
        ddl_override: str | None = None,
    ) -> SyncResult:
        connector_cls = ConnectorRegistry.get_connector(db_type)
        connector = connector_cls()
        async with connector:
            try:
                await connector.connect(config)
            except Exception as e:
                msg = f"Failed to connect to {db_type} database: {e}"
                raise ConnectionError(msg) from e

            schema_infos = await connector.extract_schemas()
            target_schemas = _filter_schemas(schema_infos, schemas)
            all_tables: list[ExtractedTable] = []

            for schema_info in target_schemas:
                table_names = await connector.extract_tables(schema_info.name)
                tables: list[ExtractedTable] = []
                for t in table_names:
                    try:
                        cols = await connector.extract_columns(schema_info.name, t.name)
                        t.columns = cols
                    except Exception as e:
                        logger.warning("Failed to extract columns for %s.%s: %s", schema_info.name, t.name, e)
                        continue
                    tables.append(t)
                all_tables.extend(tables)

            return await self._process_schema(
                schema_infos=target_schemas,
                all_tables=all_tables,
                run_annotation=run_annotation,
                run_inference=run_inference,
                ddl_override=ddl_override,
            )

    async def sync_from_tables(
        self,
        tables: list[ExtractedTable],
        run_annotation: bool = True,
        run_inference: bool = True,
    ) -> SyncResult:
        schema_info = ExtractedSchemaInfo(
            name="inferred",
            tables=tables,
        )
        return await self._process_schema(
            schema_infos=[schema_info],
            all_tables=tables,
            run_annotation=run_annotation,
            run_inference=run_inference,
        )

    async def _process_schema(
        self,
        schema_infos: list[ExtractedSchemaInfo],
        all_tables: list[ExtractedTable],
        run_annotation: bool = True,
        run_inference: bool = True,
        ddl_override: str | None = None,
    ) -> SyncResult:
        if ddl_override and self._ddl_parser:
            all_tables = self._ddl_parser.parse(ddl_override)

        current_signatures = _compute_signatures(all_tables)
        changes = _detect_changes(
            previous_signatures=self._sync_state.signatures,
            current_tables=all_tables,
            current_signatures=current_signatures,
        )

        added_or_changed = [
            c for c in changes
            if c.change_type in (SyncChangeType.ADDED, SyncChangeType.CHANGED)
        ]

        annotation_map: dict[str, Any] = {}
        if run_annotation and added_or_changed:
            tables_to_annotate = [c.table for c in added_or_changed]
            try:
                results = await self._annotation_service.annotate_batch(tables_to_annotate)
                for table, result in zip(tables_to_annotate, results, strict=False):
                    annotation_map[table.name] = result
            except Exception as e:
                logger.exception("Batch annotation failed: %s", e)

        inference_map: dict[str, list[InferredRelationship]] = {}
        if run_inference and added_or_changed:
            tables_to_infer = [c.table for c in added_or_changed]
            try:
                rels = self._inference_service.infer(tables_to_infer)
                for rel in rels:
                    inference_map.setdefault(rel.source_table, []).append(rel)
            except Exception as e:
                logger.exception("Relationship inference failed: %s", e)

        errors: list[str] = []
        for change in changes:
            if change.change_type in (SyncChangeType.ADDED, SyncChangeType.CHANGED):
                if change.table.name in annotation_map:
                    change.annotation = annotation_map[change.table.name]
                if change.table.name in inference_map:
                    change.relationships = inference_map[change.table.name]

        combined_schema = ExtractedSchemaInfo(
            name=schema_infos[0].name if schema_infos else "unknown",
            tables=all_tables,
        )

        self._sync_state.signatures.update(current_signatures)
        self._sync_state.last_synced_at = __import__(
            "datetime"
        ).datetime.now(__import__("datetime").UTC)

        return SyncResult(
            schema_info=combined_schema,
            changes=changes,
            errors=errors,
        )


def _compute_signatures(
    tables: list[ExtractedTable],
) -> dict[str, str]:
    return {t.name: table_signature(t) for t in tables}


def _detect_changes(
    previous_signatures: dict[str, str],
    current_tables: list[ExtractedTable],
    current_signatures: dict[str, str] | None = None,
) -> list[SyncChange]:
    if current_signatures is None:
        current_signatures = _compute_signatures(current_tables)

    current_names = {t.name for t in current_tables}
    previous_names = set(previous_signatures.keys())

    table_map = {t.name: t for t in current_tables}

    changes: list[SyncChange] = []

    for name in current_names:
        table = table_map[name]
        current_sig = current_signatures[name]

        if name not in previous_signatures:
            changes.append(
                SyncChange(
                    table=table,
                    change_type=SyncChangeType.ADDED,
                    current_signature=current_sig,
                )
            )
        elif previous_signatures[name] != current_sig:
            changes.append(
                SyncChange(
                    table=table,
                    change_type=SyncChangeType.CHANGED,
                    previous_signature=previous_signatures[name],
                    current_signature=current_sig,
                )
            )
        else:
            changes.append(
                SyncChange(
                    table=table,
                    change_type=SyncChangeType.UNCHANGED,
                    previous_signature=previous_signatures[name],
                    current_signature=current_sig,
                )
            )

    removed = previous_names - current_names
    for name in sorted(removed):
        changes.append(
            SyncChange(
                table=ExtractedTable(name=name, columns=[]),
                change_type=SyncChangeType.REMOVED,
                previous_signature=previous_signatures.get(name),
            )
        )

    return changes


def _filter_schemas(
    schema_infos: list[ExtractedSchemaInfo],
    schemas: list[str] | None,
) -> list[ExtractedSchemaInfo]:
    if schemas is None:
        return schema_infos
    return [s for s in schema_infos if s.name in schemas]

from __future__ import annotations

import logging
from typing import Any

from ke.stores.schema.repository import DatabaseConfigRepository
from schema_intelligence.connectors.base import ConnectorConfig
from schema_intelligence.embedding.pipeline import SchemaEmbeddingPipeline
from schema_intelligence.sync.orchestrator import SyncOrchestrator

logger = logging.getLogger(__name__)


class MetadataSyncService:
    def __init__(
        self,
        db_repo: DatabaseConfigRepository,
        sync_orchestrator: SyncOrchestrator | None = None,
        embedding_pipeline: SchemaEmbeddingPipeline | None = None,
    ) -> None:
        self._db_repo = db_repo
        self._sync_orchestrator = sync_orchestrator or SyncOrchestrator()
        self._embedding_pipeline = embedding_pipeline or SchemaEmbeddingPipeline()

    async def sync_database(
        self,
        database_id: str,
        password: str | None = None,
        run_annotation: bool = True,
        run_inference: bool = True,
    ) -> dict[str, Any]:
        db_config = await self._db_repo.get(database_id)
        if db_config is None:
            msg = f"DatabaseConfig {database_id} not found"
            raise ValueError(msg)

        await self._db_repo.update(database_id, {
            "sync_status": "syncing",
            "sync_error_message": None,
        })

        try:
            resolved_password = password or db_config.connection_options.get("password", "")
            connector_config = ConnectorConfig(
                host=db_config.host or "localhost",
                port=db_config.port or 5432,
                database=db_config.database_name or "",
                username=db_config.username or "",
                password=resolved_password,
                schema_filter=db_config.schema_filter,
                ssl=db_config.ssl_enabled,
            )

            sync_result = await self._sync_orchestrator.sync(
                config=connector_config,
                db_type=db_config.db_type,
                schemas=db_config.schema_filter,
                run_annotation=run_annotation,
                run_inference=run_inference,
            )

            embed_stats = await self._embedding_pipeline.process_sync_result(
                result=sync_result,
                tenant_id=db_config.tenant_id,
            )

            await self._db_repo.update(database_id, {
                "sync_status": "synced",
                "last_synced_at": sync_result.synced_at,
                "table_count": len(sync_result.schema_info.tables),
            })

            return {
                "database_id": database_id,
                "sync_status": "synced",
                "added": sync_result.added_count,
                "changed": sync_result.changed_count,
                "removed": sync_result.removed_count,
                "unchanged": sync_result.unchanged_count,
                "errors": list(sync_result.errors),
                "embedding": embed_stats,
                "synced_at": sync_result.synced_at.isoformat(),
            }
        except Exception as exc:
            await self._db_repo.update(database_id, {
                "sync_status": "error",
                "sync_error_message": str(exc),
            })
            raise

from __future__ import annotations

from fastapi import FastAPI

from ke.api.middleware.auth import ServiceAuthMiddleware
from ke.api.middleware.tenant import TenantMiddleware
from ke.api.routes.graph import router as graph_router
from ke.api.routes.schema import router as schema_router
from ke.api.routes.sync import router as sync_router
from ke.api.routes.vector import router as vector_router


def create_ke_api() -> FastAPI:
    app = FastAPI(
        title="Knowledge Engine API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(TenantMiddleware)
    app.add_middleware(ServiceAuthMiddleware)

    app.include_router(schema_router, prefix="/v1/ke/schema")
    app.include_router(vector_router, prefix="/v1/ke/vector")
    app.include_router(graph_router, prefix="/v1/ke/graph")
    app.include_router(sync_router, prefix="/v1/ke/sync")

    return app

from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ke.api.schemas import KEErrorCode, error_response


def _verify_service_token(token: str) -> bool:
    expected = os.environ.get("KE_API_TOKEN", "ke_dev_token_2026")
    return token == expected


class ServiceAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        token = request.headers.get("X-Service-Token")
        if not token or not _verify_service_token(token):
            resp = error_response(
                KEErrorCode.INVALID_TOKEN,
                details={"header": "X-Service-Token"},
            )
            return JSONResponse(
                status_code=401,
                content=resp.model_dump(mode="json"),
            )
        return await call_next(request)

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_token
from app.core.config import get_settings

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, str]:
    api_key = request.headers.get("x-api-key", "")
    if api_key:
        settings = get_settings()
        if api_key in settings.api_keys:
            return {"sub": "api-user", "role": "user", "tenant_id": "demo", "auth_method": "api_key"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if credentials is None:
        return {"sub": "anonymous", "role": "guest"}
    payload = decode_token(credentials.credentials)
    if payload is None:
        return {"sub": "anonymous", "role": "guest"}
    return {
        "sub": payload.get("sub", "unknown"),
        "role": payload.get("role", "user"),
        "tenant_id": payload.get("tenant_id", "demo"),
        "auth_method": "jwt",
    }


def require_role(required_role: str) -> Callable[[], Awaitable[dict[str, str]]]:
    async def role_checker(
        current_user: dict[str, str] = Depends(get_current_user),
    ) -> dict[str, str]:
        if current_user.get("role") != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker

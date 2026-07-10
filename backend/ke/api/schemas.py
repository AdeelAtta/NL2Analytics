from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import Field

from shared.models.base import BaseSchema

T = TypeVar("T")


class KEAPIError(BaseSchema):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class KEResponse(BaseSchema, Generic[T]):
    success: bool = True
    data: T | None = None
    error: KEAPIError | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class KEPaginationMeta(BaseSchema):
    page: int = 1
    page_size: int = 50
    total: int = 0
    total_pages: int = 0


class KEListResponse(KEResponse[list[T]], Generic[T]):
    meta: KEPaginationMeta = Field(default_factory=KEPaginationMeta)


class KEErrorCode:
    ENTITY_NOT_FOUND = "KE-001"
    TENANT_REQUIRED = "KE-002"
    INVALID_TOKEN = "KE-003"
    STORE_OPERATION_FAILED = "KE-004"
    QDRANT_CONNECTION_FAILED = "KE-005"
    POSTGRESQL_QUERY_FAILED = "KE-006"
    CACHE_WRITE_FAILED = "KE-007"
    EMBEDDING_SERVICE_UNAVAILABLE = "KE-008"
    VALIDATION_ERROR = "KE-009"
    INTERNAL_ERROR = "KE-500"


ERROR_MESSAGES: dict[str, str] = {
    KEErrorCode.ENTITY_NOT_FOUND: "The requested resource was not found",
    KEErrorCode.TENANT_REQUIRED: "X-Tenant-Id header is required",
    KEErrorCode.INVALID_TOKEN: "Invalid or expired service token",
    KEErrorCode.STORE_OPERATION_FAILED: "Store operation failed",
    KEErrorCode.QDRANT_CONNECTION_FAILED: "Qdrant connection failed",
    KEErrorCode.POSTGRESQL_QUERY_FAILED: "PostgreSQL query failed",
    KEErrorCode.CACHE_WRITE_FAILED: "Cache write failed",
    KEErrorCode.EMBEDDING_SERVICE_UNAVAILABLE: "Embedding service unavailable",
    KEErrorCode.VALIDATION_ERROR: "Request validation failed",
    KEErrorCode.INTERNAL_ERROR: "Internal server error",
}


def error_response(code: str, details: dict[str, Any] | None = None) -> KEResponse[None]:
    return KEResponse[None](
        success=False,
        data=None,
        error=KEAPIError(
            code=code,
            message=ERROR_MESSAGES.get(code, "Unknown error"),
            details=details or {},
        ),
    )


def success_response(data: T, meta: dict[str, Any] | None = None) -> KEResponse[T]:
    return KEResponse[T](
        success=True,
        data=data,
        meta=meta or {},
    )

from __future__ import annotations

import httpx

from ke.api.schemas import (
    ERROR_MESSAGES,
    KEErrorCode,
    error_response,
    success_response,
)


class TestAuthMiddleware:
    async def test_no_token_returns_401(self, async_ke_client: httpx.AsyncClient) -> None:
        resp = await async_ke_client.get("/v1/ke/schema/tenants")
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == KEErrorCode.INVALID_TOKEN

    async def test_invalid_token_returns_401(self, async_ke_client: httpx.AsyncClient) -> None:
        resp = await async_ke_client.get(
            "/v1/ke/schema/tenants",
            headers={"X-Service-Token": "wrong_token"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False

    async def test_valid_token_allows_request(
        self, async_ke_client_auth: httpx.AsyncClient
    ) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/tenants")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True


class TestResponseSchemas:
    def test_success_response(self) -> None:
        resp = success_response({"id": "abc"}, meta={"version": 1})
        assert resp.success is True
        assert resp.data == {"id": "abc"}
        assert resp.meta == {"version": 1}
        assert resp.error is None

    def test_error_response(self) -> None:
        resp = error_response(KEErrorCode.ENTITY_NOT_FOUND, {"id": "xyz"})
        assert resp.success is False
        assert resp.data is None
        assert resp.error is not None
        assert resp.error.code == KEErrorCode.ENTITY_NOT_FOUND
        assert resp.error.message == ERROR_MESSAGES[KEErrorCode.ENTITY_NOT_FOUND]
        assert resp.error.details == {"id": "xyz"}

    def test_unknown_error_code(self) -> None:
        resp = error_response("UNKNOWN-CODE")
        assert resp.error is not None
        assert resp.error.message == "Unknown error"


class TestSchemaRoutes:
    async def test_list_tenants(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/tenants")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 1
        assert body["data"][0]["name"] == "Test Tenant"
        assert body["data"][0]["slug"] == "test-tenant"

    async def test_list_tenants_pagination(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/tenants?page=2&page_size=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["page"] == 2
        assert body["meta"]["page_size"] == 10

    async def test_get_tenant(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/tenants/some-id")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "Test Tenant"

    async def test_get_tenant_not_found(self, async_ke_client_not_found: httpx.AsyncClient) -> None:
        resp = await async_ke_client_not_found.get("/v1/ke/schema/tenants/nonexistent")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == KEErrorCode.ENTITY_NOT_FOUND

    async def test_get_tenant_by_slug(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/tenants/by-slug/test-tenant")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["slug"] == "test-tenant"

    async def test_get_tenant_by_slug_not_found(
        self, async_ke_client_not_found: httpx.AsyncClient
    ) -> None:
        resp = await async_ke_client_not_found.get("/v1/ke/schema/tenants/by-slug/unknown")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False

    async def test_list_databases(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/databases")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 1
        assert body["data"][0]["db_type"] == "postgresql"

    async def test_get_database(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/databases/db-id")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["db_type"] == "postgresql"

    async def test_list_schemas(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/schemas")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 1

    async def test_get_schema(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/schemas/s-id")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "public"

    async def test_list_tables(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/tables")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"][0]["name"] == "users"

    async def test_get_table(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/tables/t-id")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "users"

    async def test_list_columns(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/columns")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"][0]["data_type"] == "integer"

    async def test_get_column(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/columns/c-id")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["ordinal_position"] == 1

    async def test_list_relationships(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/relationships")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"][0]["relationship_type"] == "foreign_key"

    async def test_get_relationship(self, async_ke_client_auth: httpx.AsyncClient) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/relationships/r-id")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["relationship_type"] == "foreign_key"


class TestOpenAPI:
    async def test_docs_accessible_without_auth(self, async_ke_client: httpx.AsyncClient) -> None:
        resp = await async_ke_client.get("/docs")
        assert resp.status_code == 200

    async def test_openapi_json_accessible_without_auth(
        self, async_ke_client: httpx.AsyncClient
    ) -> None:
        resp = await async_ke_client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "Knowledge Engine API"
        assert schema["info"]["version"] == "0.1.0"

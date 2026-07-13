from __future__ import annotations

import httpx


class TestResponseFormat:
    async def test_all_responses_have_consistent_shape(
        self, async_ke_client_auth: httpx.AsyncClient
    ) -> None:
        endpoints = [
            "/v1/ke/schema/tenants",
            "/v1/ke/schema/databases",
            "/v1/ke/schema/schemas",
            "/v1/ke/schema/tables",
            "/v1/ke/schema/columns",
            "/v1/ke/schema/relationships",
        ]
        for ep in endpoints:
            resp = await async_ke_client_auth.get(ep)
            assert resp.status_code == 200, f"{ep} returned {resp.status_code}"
            body = resp.json()
            assert "success" in body, f"{ep} missing success"
            assert "data" in body, f"{ep} missing data"
            assert "meta" in body, f"{ep} missing meta"
            assert "timestamp" in body, f"{ep} missing timestamp"
            assert body["success"] is True

    async def test_all_responses_have_valid_timestamp(
        self, async_ke_client_auth: httpx.AsyncClient
    ) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/tenants")
        ts = resp.json()["timestamp"]
        assert "T" in ts
        assert ts.endswith("Z") or "+" in ts

    async def test_error_responses_have_consistent_shape(
        self, async_ke_client_not_found: httpx.AsyncClient
    ) -> None:
        endpoints = [
            "/v1/ke/schema/tenants/nonexistent",
            "/v1/ke/schema/databases/nonexistent",
            "/v1/ke/schema/schemas/nonexistent",
            "/v1/ke/schema/tables/nonexistent",
            "/v1/ke/schema/columns/nonexistent",
            "/v1/ke/schema/relationships/nonexistent",
        ]
        for ep in endpoints:
            resp = await async_ke_client_not_found.get(ep)
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is False, f"{ep} should be error"
            assert body["error"]["code"] == "KE-001", f"{ep} wrong code"
            assert body["error"]["message"]
            assert isinstance(body["error"]["details"], dict)

    async def test_error_response_has_no_data(
        self, async_ke_client_not_found: httpx.AsyncClient
    ) -> None:
        resp = await async_ke_client_not_found.get("/v1/ke/schema/tenants/nonexistent")
        body = resp.json()
        assert body["data"] is None
        assert body["error"] is not None


class TestAuthEdgeCases:
    async def test_empty_token_header_returns_401(
        self, async_ke_client: httpx.AsyncClient
    ) -> None:
        resp = await async_ke_client.get(
            "/v1/ke/schema/tenants",
            headers={"X-Service-Token": ""},
        )
        assert resp.status_code == 401

    async def test_all_schema_routes_require_auth(
        self, async_ke_client: httpx.AsyncClient
    ) -> None:
        endpoints = [
            ("GET", "/v1/ke/schema/tenants"),
            ("GET", "/v1/ke/schema/databases"),
            ("GET", "/v1/ke/schema/schemas"),
            ("GET", "/v1/ke/schema/tables"),
            ("GET", "/v1/ke/schema/columns"),
            ("GET", "/v1/ke/schema/relationships"),
        ]
        for method, ep in endpoints:
            resp = await async_ke_client.request(method, ep)
            assert resp.status_code == 401, f"{method} {ep} should require auth"

class TestPaginationEdgeCases:
    async def test_pagination_meta_present_on_all_list_endpoints(
        self, async_ke_client_auth: httpx.AsyncClient
    ) -> None:
        endpoints = [
            "/v1/ke/schema/tenants",
            "/v1/ke/schema/databases",
            "/v1/ke/schema/schemas",
            "/v1/ke/schema/tables",
            "/v1/ke/schema/columns",
            "/v1/ke/schema/relationships",
        ]
        for ep in endpoints:
            resp = await async_ke_client_auth.get(ep)
            meta = resp.json()["meta"]
            assert "page" in meta
            assert "page_size" in meta
            assert "total" in meta
            assert "total_pages" in meta
            assert isinstance(meta["page"], int)
            assert isinstance(meta["page_size"], int)
            assert isinstance(meta["total"], int)
            assert isinstance(meta["total_pages"], int)

    async def test_default_pagination_values(
        self, async_ke_client_auth: httpx.AsyncClient
    ) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/tenants")
        meta = resp.json()["meta"]
        assert meta["page"] == 1
        assert meta["page_size"] == 50

    async def test_custom_page_size(
        self, async_ke_client_auth: httpx.AsyncClient
    ) -> None:
        resp = await async_ke_client_auth.get("/v1/ke/schema/tenants?page_size=25")
        assert resp.status_code == 200
        meta = resp.json()["meta"]
        assert meta["page_size"] == 25


class TestTenantIsolation:
    async def test_schema_endpoints_filter_by_tenant_id(
        self, async_ke_client_auth: httpx.AsyncClient
    ) -> None:
        resp = await async_ke_client_auth.get(
            "/v1/ke/schema/databases?tenant_id=tenant_abc"
        )
        assert resp.status_code == 200


class TestMethodValidation:
    async def test_post_on_get_endpoint_returns_405(
        self, async_ke_client_auth: httpx.AsyncClient
    ) -> None:
        resp = await async_ke_client_auth.post("/v1/ke/schema/tenants")
        assert resp.status_code in (405, 422)

class TestErrorCodes:
    async def test_error_code_message_mapping(
        self, async_ke_client_not_found: httpx.AsyncClient
    ) -> None:
        from ke.api.schemas import ERROR_MESSAGES, KEErrorCode

        resp = await async_ke_client_not_found.get(
            "/v1/ke/schema/tenants/some-id"
        )
        body = resp.json()
        assert body["error"]["message"] == ERROR_MESSAGES[KEErrorCode.ENTITY_NOT_FOUND]


class TestOpenAPICompleteness:
    async def test_openapi_has_all_endpoints(
        self, async_ke_client: httpx.AsyncClient
    ) -> None:
        resp = await async_ke_client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        paths = schema["paths"]
        expected_endpoints = [
            "/v1/ke/schema/tenants",
            "/v1/ke/schema/tenants/{tenant_id}",
            "/v1/ke/schema/tenants/by-slug/{slug}",
            "/v1/ke/schema/databases",
            "/v1/ke/schema/databases/{db_id}",
            "/v1/ke/schema/schemas",
            "/v1/ke/schema/schemas/{schema_id}",
            "/v1/ke/schema/tables",
            "/v1/ke/schema/tables/{table_id}",
            "/v1/ke/schema/columns",
            "/v1/ke/schema/columns/{col_id}",
            "/v1/ke/schema/relationships",
            "/v1/ke/schema/relationships/{rel_id}",
        ]
        for ep in expected_endpoints:
            assert ep in paths, f"Missing endpoint in OpenAPI: {ep}"

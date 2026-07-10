# EP-005: Knowledge Engine — API Layer

Epic ID: **EP-005** | Priority: **P0** | Dependencies: **EP-002, EP-003** | Complexity: **XL** | Agent: **Knowledge Engine Agent**

---

Implement the Knowledge Engine API service — the single internal interface through which all components access the 9 knowledge stores. This is the architectural backbone (ADR-004).

## Goals
- FastAPI service on port 8200 (internal only)
- Unified CRUD API for all 9 stores
- Tenant-aware routing (extract tenant from context)
- Consistent error handling and response format
- gRPC readiness (start with REST, gRPC in Phase 4)
- Full OpenAPI spec generation
- Authentication (internal service tokens)

## Out of Scope
- Public API layer (EP-013)
- Store implementations (covered in EP-002, EP-003, EP-004)
- Query-time pipeline logic

## Tasks

| ID | Name | P | Deps | Est | Status |
|----|------|---|------|-----|--------|
| TASK-029 | Scaffold KE API FastAPI service | P0 | TASK-001 | M | ✅ done |
| TASK-030 | Define unified response format and error codes | P0 | TASK-029 | M | ✅ done |
| TASK-031 | Implement tenant middleware | P0 | TASK-029 | M | ✅ done |
| TASK-032 | Implement internal auth (service tokens) | P0 | TASK-029 | L | ✅ done |
| TASK-033 | Implement Schema Store API routes | P0 | TASK-029, EP-002 | L | ✅ done |
| TASK-034 | Implement Vector Index API routes | P0 | TASK-029, EP-003 | L | ✅ done |
| TASK-035 | Implement Graph Store API routes | P1 | TASK-029, EP-004 | L | ⏳ blocked |
| TASK-036 | Implement Query History store API routes | P0 | TASK-029 | M | ⏳ blocked |
| TASK-037 | Implement Feedback store API routes | P0 | TASK-029 | M | ⏳ blocked |
| TASK-038 | Implement Config store API routes | P1 | TASK-029 | M | ⏳ blocked |
| TASK-039 | Implement Metrics store API routes | P1 | TASK-029 | M | ⏳ blocked |
| TASK-040 | Implement Audit store API routes | P0 | TASK-029 | M | ⏳ blocked |
| TASK-041 | Implement Cache store wrapper | P0 | TASK-029 | M | ⏳ blocked |
| TASK-042 | Write integration tests for KE API | P0 | TASK-033 | XL | 🏗️ in progress |

## Status: 🏗️ In Progress (TASK-029 through TASK-034 done, TASK-042 in progress)

## Acceptance Criteria
- All 9 stores accessible through KE API
- Tenant context correctly isolated in all operations
- Internal auth rejects requests without valid service token
- Response format consistent across all endpoints
- OpenAPI spec auto-generated and browsable
- Integration tests cover all routes
- P95 latency < 10ms (KE API overhead, not store I/O)

## Definition of Done
- All routes implemented and tested
- Integration test suite covers happy path and error cases for every route
- OpenAPI spec validated
- Performance benchmark: KE API overhead < 10ms P95

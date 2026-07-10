from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from ke.models.schema import Column, Table
from ke.services.quality import (
    QualityScoreService,
    _score_completeness,
    _score_consistency,
    _score_coverage,
    _score_freshness,
)

_NOW = datetime.now(UTC)


def _make_table(
    id: str = "t1",
    schema_id: str = "s1",
    name: str = "users",
    description: str | None = "User accounts",
    last_introspected_at: datetime | None = None,
) -> Table:
    return Table(
        id=id,
        schema_id=schema_id,
        name=name,
        description=description,
        row_estimate=0,
        version=1,
        is_active=True,
        last_introspected_at=last_introspected_at,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_column(
    id: str = "c1",
    table_id: str = "t1",
    name: str = "id",
    data_type: str = "integer",
    is_primary_key: bool = False,
    description: str | None = None,
    default_value: str | None = None,
    character_maximum_length: int | None = None,
    numeric_precision: int | None = None,
    numeric_scale: int | None = None,
) -> Column:
    return Column(
        id=id,
        table_id=table_id,
        name=name,
        ordinal_position=1,
        data_type=data_type,
        is_nullable=True,
        is_primary_key=is_primary_key,
        is_unique=False,
        default_value=default_value,
        description=description,
        character_maximum_length=character_maximum_length,
        numeric_precision=numeric_precision,
        numeric_scale=numeric_scale,
        created_at=_NOW,
        updated_at=_NOW,
    )


class TestScoreCoverage:
    def test_empty_tables(self):
        assert _score_coverage([], []) == 0.0

    def test_full_coverage(self):
        tables = [_make_table(description="desc")]
        columns = [_make_column(description="desc", is_primary_key=True)]
        score = _score_coverage(tables, columns)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_no_coverage(self):
        tables = [_make_table(description=None)]
        columns = [_make_column(description=None)]
        score = _score_coverage(tables, columns)
        assert score < 0.5


class TestScoreCompleteness:
    def test_empty_columns(self):
        assert _score_completeness([], []) == 0.0

    def test_full_completeness(self):
        columns = [_make_column(description="A column that stores user email addresses.", character_maximum_length=255)]
        score = _score_completeness([], columns)
        assert score > 0.5

    def test_minimal_column(self):
        columns = [_make_column(description=None)]
        score = _score_completeness([], columns)
        assert score == 0.0


class TestScoreConsistency:
    def test_empty_columns(self):
        assert _score_consistency([], []) == 0.0

    def test_consistent(self):
        columns = [_make_column(name="email", data_type="varchar")]
        score = _score_consistency([], columns)
        assert score > 0.5

    def test_inconsistent(self):
        columns = [_make_column(name="Full Name", data_type="custom_type")]
        score = _score_consistency([], columns)
        assert score < 0.5


class TestScoreFreshness:
    def test_no_sync_times(self):
        tables = [_make_table(last_introspected_at=None)]
        assert _score_freshness(tables) == 0.0

    def test_recently_synced(self):
        tables = [_make_table(last_introspected_at=_NOW - timedelta(minutes=30))]
        assert _score_freshness(tables) == 1.0

    def test_old_sync(self):
        tables = [_make_table(last_introspected_at=_NOW - timedelta(days=60))]
        assert _score_freshness(tables) == 0.0


class TestQualityScoreService:
    @pytest.fixture
    def service(self):
        table_repo = MagicMock()
        table_repo.list = AsyncMock(return_value=([], 0))
        col_repo = MagicMock()
        col_repo.list_by_table = AsyncMock(return_value=[])
        return QualityScoreService(table_repo=table_repo, column_repo=col_repo)

    async def test_empty_tenant(self, service):
        result = await service.score_tenant("tenant1")
        assert result["overall"] == 0.0
        assert result["details"]["total_tables"] == 0

    async def test_tenant_with_data(self, service):
        tables = [
            _make_table(id="t1", name="users", description="User accounts"),
            _make_table(id="t2", name="orders", description=None),
        ]
        columns_t1 = [
            _make_column(id="c1", table_id="t1", name="id", data_type="integer", is_primary_key=True, description="Primary key"),
            _make_column(id="c2", table_id="t1", name="email", data_type="varchar(255)", description="Email address"),
        ]
        columns_t2 = [
            _make_column(id="c3", table_id="t2", name="id", data_type="integer", is_primary_key=True),
            _make_column(id="c4", table_id="t2", name="total", data_type="numeric"),
        ]

        def list_by_table_side_effect(table_id):
            if table_id == "t1":
                return columns_t1
            return columns_t2

        service._table_repo.list = AsyncMock(return_value=(tables, 2))
        service._column_repo.list_by_table = AsyncMock(side_effect=list_by_table_side_effect)

        result = await service.score_tenant("tenant1")
        assert result["overall"] > 0
        assert result["dimensions"]["coverage"] > 0
        assert result["details"]["total_tables"] == 2
        assert result["details"]["total_columns"] == 4

    async def test_tenant_score_range(self, service):
        tables = [_make_table(id="t1", name="users", description="desc")]
        columns = [_make_column(table_id="t1", description="A detailed description.", is_primary_key=True, character_maximum_length=255)]
        service._table_repo.list = AsyncMock(return_value=(tables, 1))
        service._column_repo.list_by_table = AsyncMock(return_value=columns)

        result = await service.score_tenant("tenant1")
        assert 0.0 <= result["overall"] <= 1.0
        for dim, score in result["dimensions"].items():
            assert 0.0 <= score <= 1.0, f"Dimension {dim} has score {score} out of range"

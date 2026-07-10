"""Create schema_versions table for versioned DDL history.

Revision ID: 002
Revises: 001
Create Date: 2026-07-11

"""
# ruff: noqa: E501
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schema_versions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("schema_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("ddl_snapshot", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(100), nullable=False, server_default="connector"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["schema_id"], ["schema_store.schema_infos.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("schema_id", "version", name="uq_schema_versions_version"),
        schema="schema_store",
    )
    op.create_index("idx_schema_versions_schema", "schema_versions", ["schema_id"], schema="schema_store")
    op.create_index("idx_schema_versions_created", "schema_versions", ["created_at"], schema="schema_store")

    op.execute("""
        ALTER TABLE schema_store.schema_versions ENABLE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation_inherited ON schema_store.schema_versions
            AS PERMISSIVE FOR ALL TO public
            USING (
                EXISTS (
                    SELECT 1 FROM schema_store.schema_infos
                    JOIN schema_store.databases ON databases.id = schema_infos.database_id
                    WHERE schema_infos.id = schema_versions.schema_id
                      AND databases.tenant_id = current_setting('app.tenant_id')::UUID
                )
            );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS schema_store.schema_versions CASCADE")

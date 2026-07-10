"""Create graph_store schema with graph_nodes and graph_edges tables.

Revision ID: 003
Revises: 002
Create Date: 2026-07-11

"""
# ruff: noqa: E501
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS graph_store")

    op.create_table(
        "graph_nodes",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("properties", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "node_type IN ('table', 'column', 'domain', 'concept', 'glossary_term', 'query_pattern')",
            name="ck_graph_nodes_type",
        ),
        schema="graph_store",
    )
    op.create_index("idx_graph_nodes_tenant", "graph_nodes", ["tenant_id"], schema="graph_store")
    op.create_index("idx_graph_nodes_type", "graph_nodes", ["node_type"], schema="graph_store")
    op.create_index("idx_graph_nodes_external", "graph_nodes", ["external_id"], schema="graph_store")
    op.create_index("idx_graph_nodes_name_trgm", "graph_nodes", ["name"],
                    postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}, schema="graph_store")

    op.create_table(
        "graph_edges",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("public.tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_node_id", sa.Uuid(), sa.ForeignKey("graph_store.graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), sa.ForeignKey("graph_store.graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("edge_type", sa.String(50), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("properties", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "edge_type IN ('belongs_to', 'references', 'maps_to', 'frequently_joined', 'semantic_parent')",
            name="ck_graph_edges_type",
        ),
        schema="graph_store",
    )
    op.create_index("idx_graph_edges_tenant", "graph_edges", ["tenant_id"], schema="graph_store")
    op.create_index("idx_graph_edges_source", "graph_edges", ["source_node_id"], schema="graph_store")
    op.create_index("idx_graph_edges_target", "graph_edges", ["target_node_id"], schema="graph_store")
    op.create_index("idx_graph_edges_type", "graph_edges", ["edge_type"], schema="graph_store")
    op.create_index("idx_graph_edges_source_type", "graph_edges", ["source_node_id", "edge_type"], schema="graph_store")

    op.execute("""
        ALTER TABLE graph_store.graph_nodes ENABLE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation_nodes ON graph_store.graph_nodes
            AS PERMISSIVE FOR ALL TO public
            USING (tenant_id = current_setting('app.tenant_id')::UUID);
    """)
    op.execute("""
        ALTER TABLE graph_store.graph_edges ENABLE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation_edges ON graph_store.graph_edges
            AS PERMISSIVE FOR ALL TO public
            USING (tenant_id = current_setting('app.tenant_id')::UUID);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS graph_store.graph_edges CASCADE")
    op.execute("DROP TABLE IF EXISTS graph_store.graph_nodes CASCADE")
    op.execute("DROP SCHEMA IF EXISTS graph_store CASCADE")

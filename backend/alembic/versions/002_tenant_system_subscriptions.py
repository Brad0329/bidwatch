"""Add tenant_system_subscriptions table.

Revision ID: 002
Revises: 001
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"


def upgrade() -> None:
    op.create_table(
        "tenant_system_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("system_source_id", sa.Integer(), sa.ForeignKey("system_sources.id"), nullable=False),
        sa.Column("subscribed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_tenant_system_sub",
        "tenant_system_subscriptions",
        ["tenant_id", "system_source_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("tenant_system_subscriptions")

"""Add nara_prespec system source.

Revision ID: 003
Revises: 002
"""

from alembic import op

revision = "003"
down_revision = "002"


def upgrade() -> None:
    op.execute(
        "INSERT INTO system_sources (name, collector_type) VALUES "
        "('나라장터 사전규격', 'nara_prespec')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_sources WHERE collector_type = 'nara_prespec'")

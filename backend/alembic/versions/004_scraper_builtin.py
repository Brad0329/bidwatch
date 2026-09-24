"""scraper_registry: is_builtin 추가 + created_by_tenant_id NULL 허용 (기본 제공 사이트).

Revision ID: 004
Revises: 003
"""

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"


def upgrade() -> None:
    op.add_column(
        "scraper_registry",
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("scraper_registry", "created_by_tenant_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # 기본 제공 행은 만든 회사가 없다(NULL) — NOT NULL로 되돌릴 수 없으니 조용히 지우지 말고 멈춘다
    conn = op.get_bind()
    orphan = conn.execute(
        sa.text("SELECT count(*) FROM scraper_registry WHERE created_by_tenant_id IS NULL")
    ).scalar()
    if orphan:
        raise RuntimeError(
            f"created_by_tenant_id가 NULL인 스크래퍼 {orphan}개가 있어 되돌릴 수 없다 — "
            "기본 제공 사이트를 먼저 정리(구독·수집 공고 포함)하거나 백업에서 복원할 것"
        )
    op.alter_column("scraper_registry", "created_by_tenant_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("scraper_registry", "is_builtin")

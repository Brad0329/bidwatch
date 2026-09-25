"""bid_notices.superseded — 나라장터 변경·재·취소공고의 이전 차수 표시 (F-017, SCHEMA.md 2026-09-25).

값은 수집 저장 직후 services/collection.refresh_revisions()가 extra 원문(bidNtceNo·bidNtceOrd)으로 채운다.
마이그레이션은 컬럼만 추가한다 — 기존 행은 backend/scripts/backfill_revisions.py(같은 함수)로 채운다.

Revision ID: 006
Revises: 005
"""

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"


def upgrade() -> None:
    op.add_column(
        "bid_notices",
        sa.Column("superseded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    # 값은 extra에서 다시 계산할 수 있어 잃는 데이터가 없다
    op.drop_column("bid_notices", "superseded")

"""Add alio system source — 알리오 공공기관 입찰공고 (bid-collectors v1.2.0 AlioCollector).

Revision ID: 005
Revises: 004
"""

import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"


def upgrade() -> None:
    op.execute(
        "INSERT INTO system_sources (name, collector_type) VALUES "
        "('알리오 공공기관 입찰공고', 'alio')"
    )


def downgrade() -> None:
    # 수집된 공고·구독이 이 행을 참조한다 — 조용히 지우지 말고 멈춘다(004와 같은 원칙)
    conn = op.get_bind()
    refs = conn.execute(sa.text(
        "SELECT (SELECT count(*) FROM bid_notices n JOIN system_sources s ON s.id = n.source_id "
        "        WHERE s.collector_type = 'alio') "
        "     + (SELECT count(*) FROM tenant_system_subscriptions t JOIN system_sources s "
        "        ON s.id = t.system_source_id WHERE s.collector_type = 'alio')"
    )).scalar()
    if refs:
        raise RuntimeError(
            f"알리오 출처를 참조하는 공고·구독 {refs}건이 있어 되돌릴 수 없다 — 먼저 정리하거나 백업에서 복원할 것"
        )
    op.execute("DELETE FROM system_sources WHERE collector_type = 'alio'")

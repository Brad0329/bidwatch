"""Add institution system sources — LH·가스공사·국방전자조달·수자원공사 (bid-collectors v1.4.0).

Revision ID: 007
Revises: 006
"""

import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"

SOURCES = (
    ("LH 입찰공고", "lh"),
    ("한국가스공사 입찰공고", "kogas"),
    ("국방전자조달 입찰공고", "d2b"),
    ("한국수자원공사 입찰공고", "kwater"),
)
TYPES = tuple(t for _, t in SOURCES)


def upgrade() -> None:
    conn = op.get_bind()
    for name, collector_type in SOURCES:
        conn.execute(sa.text("INSERT INTO system_sources (name, collector_type) VALUES (:n, :t)"),
                     {"n": name, "t": collector_type})


def downgrade() -> None:
    # 수집된 공고·구독이 이 행들을 참조한다 — 조용히 지우지 말고 멈춘다(005와 같은 원칙)
    conn = op.get_bind()
    refs = conn.execute(sa.text(
        "SELECT (SELECT count(*) FROM bid_notices n JOIN system_sources s ON s.id = n.source_id "
        "        WHERE s.collector_type = ANY(:types)) "
        "     + (SELECT count(*) FROM tenant_system_subscriptions t JOIN system_sources s "
        "        ON s.id = t.system_source_id WHERE s.collector_type = ANY(:types))"
    ), {"types": list(TYPES)}).scalar()
    if refs:
        raise RuntimeError(
            f"기관 출처를 참조하는 공고·구독 {refs}건이 있어 되돌릴 수 없다 — 먼저 정리하거나 백업에서 복원할 것"
        )
    conn.execute(sa.text("DELETE FROM system_sources WHERE collector_type = ANY(:types)"), {"types": list(TYPES)})

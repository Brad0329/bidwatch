"""공공 출처 수집기 매핑(COLLECTOR_MAP) 검증 — 손으로 쓴 표라 실제 DB·패키지와 대조한다."""

import pytest
from sqlalchemy import select

from app.database import get_session_factory
from app.models.notice import SystemSource
from app.tasks.collect_api import COLLECTOR_MAP, _get_collector


@pytest.mark.asyncio
async def test_every_system_source_has_a_constructible_collector(monkeypatch):
    """DB의 모든 collector_type이 매핑에 있고, 그 수집기가 실제로 만들어진다(키가 필요한 것은 가짜 키로)."""
    from app.config import settings
    for _, _, env_key in COLLECTOR_MAP.values():
        if env_key:
            monkeypatch.setattr(settings, env_key, "test-key", raising=False)

    async with get_session_factory()() as db:
        types = {t for (t,) in (await db.execute(select(SystemSource.collector_type))).all()}
    assert "alio" in types  # 005 마이그레이션이 적용된 DB여야 한다
    missing = types - COLLECTOR_MAP.keys()
    assert not missing, f"매핑에 없는 collector_type: {missing}"
    for t in types:
        assert _get_collector(t) is not None


def test_alio_collector_needs_no_api_key():
    collector = _get_collector("alio")
    assert type(collector).__name__ == "AlioCollector"
    assert collector.api_key is None

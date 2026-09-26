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


def test_skip_detail_types_are_consistent_with_collector_map():
    """상세 조회 제외 목록(SKIP_DETAIL_TYPES)도 손으로 쓴 표다 — 새 출처를 빠뜨린 실사례(nara만 넣고 nara_prespec 누락, 5498447).

    ① 제외 목록의 모든 값이 실제 collector_type이다(오타·삭제된 출처 방지)
    ② 같은 수집기 클래스를 쓰는 collector_type끼리는 제외 여부가 같다 — nara·nara_prespec은 NaraCollector 하나를 쓴다.
    """
    from app.services.notice import SKIP_DETAIL_TYPES

    unknown = SKIP_DETAIL_TYPES - COLLECTOR_MAP.keys()
    assert not unknown, f"COLLECTOR_MAP에 없는 제외 대상: {unknown}"

    by_class: dict[tuple[str, str], set[str]] = {}
    for t, (module, cls, _) in COLLECTOR_MAP.items():
        by_class.setdefault((module, cls), set()).add(t)
    for (_, cls), types in by_class.items():
        skipped = types & SKIP_DETAIL_TYPES
        assert skipped in (set(), types), f"{cls}를 쓰는 {sorted(types)} 중 {sorted(skipped)}만 상세 조회 제외"


def test_alio_collector_needs_no_api_key():
    collector = _get_collector("alio")
    assert type(collector).__name__ == "AlioCollector"
    assert collector.api_key is None

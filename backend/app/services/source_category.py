"""공공 출처의 묶음 — 입찰 공고(bid) / 지원사업(support).

BidWatch는 입찰 전문이고 지원사업은 선택 구독이다(2026-09-25 사용자 결정, REQUIREMENTS F-004).
이 목록이 유일한 정의다 — 화면은 API의 category·source_category를 받아 쓴다(프론트에 같은 목록을 두지 않는다).
"""

SUPPORT_COLLECTOR_TYPES = frozenset({"kstartup", "bizinfo", "smes", "subsidy24"})


def source_category(collector_type: str | None) -> str:
    return "support" if collector_type in SUPPORT_COLLECTOR_TYPES else "bid"

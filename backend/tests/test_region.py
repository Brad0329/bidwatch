import pytest

from app.services.region import REGIONS, normalize_region


@pytest.mark.parametrize(
    "raw,expected",
    [
        # 정확 일치
        ("서울특별시", "서울"),
        ("전라남도", "전남"),
        ("경상북도", "경북"),
        ("강원특별자치도", "강원"),
        ("전북특별자치도", "전북"),
        ("서울", "서울"),
        # 접두어 일치 — 시군구가 붙은 실제 수집 데이터
        ("전라남도 여수시", "전남"),
        ("충청남도 공주시", "충남"),
        ("경상남도 산청군", "경남"),
        ("경상북도 경주시", "경북"),
        ("서울특별시 강남구", "서울"),
        ("광주광역시 북구", "광주"),
        # 부분 일치 — 기관명 뒤에 지역이 오는 경우
        ("재단법인 광주광역시 사회서비스원 효령노인복지타운", "광주"),
        # 지역이 아닌 값은 원본 유지
        ("각 수요기관", "각 수요기관"),
        ("한국환경공단", "한국환경공단"),
        ("기후에너지환경부 국립환경과학원", "기후에너지환경부 국립환경과학원"),
        # 빈 값
        ("", ""),
        (None, None),
    ],
)
def test_normalize_region(raw, expected):
    assert normalize_region(raw) == expected


def test_gwangju_is_not_confused_with_gyeonggi():
    """경기도 광주시는 광주광역시가 아니다 — 긴 별칭 우선 매칭 회귀 방지."""
    assert normalize_region("경기도 광주시") == "경기"
    assert normalize_region("경기 광주시") == "경기"
    assert normalize_region("광주광역시") == "광주"


def test_jeonnam_gwangju_unified_city_is_jeonnam():
    """전남광주통합특별시는 광주 구 소재여도 전남 (2026-09-25 사용자 결정) — 기관명 중간에 있어도."""
    assert normalize_region("전남광주통합특별시 북구") == "전남"
    assert normalize_region("전남광주통합특별시") == "전남"
    assert normalize_region("재단법인 전남광주통합특별시 문화재단") == "전남"


def test_normalize_strips_whitespace():
    assert normalize_region("  전라남도 순천시  ") == "전남"


def test_all_aliases_normalize_into_known_regions():
    """정규화 결과는 항상 REGIONS 안에 있거나(지역), 원본 그대로여야 한다."""
    for region in REGIONS:
        assert normalize_region(region) == region

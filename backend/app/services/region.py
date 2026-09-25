"""지역(region) 정규화 유틸."""

# 정규화된 17개 시/도 목록 (프론트 드롭다운용)
REGIONS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
]

# 17개 시/도 정규화 매핑 — 다양한 표기를 짧은 이름으로 통일
_REGION_ALIASES: dict[str, str] = {
    # 특별시·광역시·특별자치시
    "서울특별시": "서울",
    "서울시": "서울",
    "서울": "서울",
    "부산광역시": "부산",
    "부산시": "부산",
    "부산": "부산",
    "대구광역시": "대구",
    "대구시": "대구",
    "대구": "대구",
    "인천광역시": "인천",
    "인천시": "인천",
    "인천": "인천",
    "광주광역시": "광주",
    "광주시": "광주",
    "광주": "광주",
    "대전광역시": "대전",
    "대전시": "대전",
    "대전": "대전",
    "울산광역시": "울산",
    "울산시": "울산",
    "울산": "울산",
    "세종특별자치시": "세종",
    "세종시": "세종",
    "세종": "세종",
    # 도·특별자치도
    "경기도": "경기",
    "경기": "경기",
    "강원특별자치도": "강원",
    "강원도": "강원",
    "강원": "강원",
    "충청북도": "충북",
    "충북": "충북",
    "충청남도": "충남",
    "충남": "충남",
    "전북특별자치도": "전북",
    "전라북도": "전북",
    "전북": "전북",
    "전라남도": "전남",
    "전남": "전남",
    "경상북도": "경북",
    "경북": "경북",
    "경상남도": "경남",
    "경남": "경남",
    "제주특별자치도": "제주",
    "제주도": "제주",
    "제주": "제주",
}

# 접두어 매칭용 — 긴 별칭부터 검사해야 "경기도 광주시"가 "광주"로 잘못 잡히지 않는다.
_ALIASES_BY_LENGTH = sorted(_REGION_ALIASES.items(), key=lambda kv: -len(kv[0]))

# 기관명 뒤에 지역이 오는 경우("재단법인 광주광역시 사회서비스원")를 위한 부분 매칭용.
# "경기"가 "OO경기장"에 걸리는 오탐을 막기 위해 4자 이상 전체 명칭만 사용한다.
_UNAMBIGUOUS_ALIASES = [(a, s) for a, s in _ALIASES_BY_LENGTH if len(a) >= 4]


def notice_region(region: str | None, extra: dict | None) -> str | None:
    """공고 1건의 저장용 지역. 나라장터 공사는 수요기관명(bid-collectors가 region에 넣는 값)이 아니라
    공사현장 지역(extra.cnstrtsiteRgnNm)을 쓴다 — 없으면 region으로 대체 (F-011, 2026-09-25).
    수집(collection.py)과 소급(scripts/backfill_regions.py)이 같이 쓴다."""
    site = (extra or {}).get("cnstrtsiteRgnNm")
    if isinstance(site, str) and site.strip():
        return normalize_region(site)
    return normalize_region(region)


def normalize_region(raw: str | None) -> str | None:
    """수집된 region 문자열을 정규화된 짧은 이름으로 변환.

    수집기가 주는 값은 "서울"처럼 짧기도 하고 "전라남도 여수시"처럼 시군구가
    붙거나 "재단법인 광주광역시 사회서비스원"처럼 기관명에 섞여 오기도 한다.
    아래 순서로 시도하고 어디에도 걸리지 않으면 원본을 유지한다
    ("각 수요기관", "한국환경공단" 등 지역이 아닌 값).

    1. 정확 일치     "전라남도"                -> "전남"
    2. 접두어 일치   "전라남도 여수시"          -> "전남"
    3. 부분 일치     "재단법인 광주광역시 ..."  -> "광주"
    """
    if not raw:
        return raw

    stripped = raw.strip()

    exact = _REGION_ALIASES.get(stripped)
    if exact:
        return exact

    for alias, short in _ALIASES_BY_LENGTH:
        if stripped.startswith(alias):
            return short

    for alias, short in _UNAMBIGUOUS_ALIASES:
        if alias in stripped:
            return short

    return stripped

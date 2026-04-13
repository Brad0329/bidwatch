"""AI 스크래퍼 설정 생성 서비스.

URL → HTML fetch → Claude API → scraper_config JSON
"""

import hashlib
import json
import logging
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import httpx

from app.config import settings

logger = logging.getLogger("bidwatch.scraper_ai")

# Claude에게 보낼 시스템 프롬프트
SCRAPER_ANALYSIS_PROMPT = """당신은 웹 게시판의 HTML 구조를 분석하여 스크래핑 설정(JSON)을 생성하는 전문가입니다.

아래 HTML을 분석하여, 이 게시판에서 공고/게시글 목록을 추출할 수 있는 scraper_config JSON을 생성하세요.

## 출력 형식 (JSON만 출력, 다른 텍스트 없이)

```json
{
  "name": "기관/사이트명",
  "source_key": "짧은영문키 (예: kocca, itp)",
  "list_url": "게시판 목록 URL (아래 제공됨)",
  "list_selector": "행(row)을 선택하는 CSS 셀렉터 (예: table tbody tr)",
  "title_selector": "제목 요소의 CSS 셀렉터 (예: td:nth-child(2) a)",
  "date_selector": "날짜 요소의 CSS 셀렉터 (예: td:nth-child(5))",
  "link_attr": "링크 속성 (기본: href)",
  "link_base": "상대URL을 절대URL로 변환할 base URL",
  "pagination": "페이지네이션 URL 패턴 (예: ?page={page})",
  "max_pages": 3,
  "encoding": "utf-8 또는 euc-kr",
  "skip_no_date": true
}
```

## 선택적 필드 (필요한 경우만 포함)
- "link_js_regex": "JavaScript 함수에서 ID를 추출하는 정규식"
- "link_template": "추출된 ID로 URL을 생성하는 템플릿 ({id} 치환)"
- "session_init_url": "쿠키 획득을 위한 초기 요청 URL"
- "post_data": "POST 요청이 필요한 경우의 form data (dict)"
- "post_json": "true면 JSON body, false면 form data"
- "page_param_key": "POST data 내 페이지 번호 키"
- "grid_selector": "데이터 영역을 감싸는 컨테이너 CSS 셀렉터"
- "offset_size": "offset 기반 페이지네이션 시 한 페이지 건수"
- "parser": "html.parser 또는 lxml (기본: html.parser)"

## 분석 규칙
1. 테이블(table) 기반이면 list_selector는 "table tbody tr" 패턴
2. div/ul 기반 목록이면 해당 컨테이너의 반복 요소를 찾으세요
3. 날짜는 보통 yyyy-MM-dd, yyyy.MM.dd, yyyyMMdd 형식입니다
4. JavaScript onclick 등으로 링크가 구성된 경우 link_js_regex를 사용하세요
5. 빈 행이나 헤더 행이 포함될 수 있으므로 title_selector는 정확히 지정하세요
6. JSON만 출력하세요. 설명, 마크다운 코드블록 없이 순수 JSON만."""


def normalize_url(url: str) -> str:
    """URL을 정규화하여 중복 등록을 방지."""
    parsed = urlparse(url)

    # scheme을 소문자로
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()

    # trailing slash 제거
    path = parsed.path.rstrip("/") or "/"

    # 추적 파라미터 제거
    tracking_params = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in params.items() if k not in tracking_params}
        query = urlencode(filtered, doseq=True)
    else:
        query = ""

    return urlunparse((scheme, netloc, path, "", query, ""))


def hash_url(url: str) -> str:
    """정규화된 URL의 SHA256 해시."""
    return hashlib.sha256(url.encode()).hexdigest()


async def fetch_page_html(url: str, timeout: int = 15) -> str:
    """URL의 HTML을 가져와서 script/style 태그를 제거하고 반환."""
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    html = resp.text

    # script, style 태그 제거
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # 50K로 truncate (Claude 컨텍스트 절약)
    if len(html) > 50000:
        html = html[:50000]

    return html


async def analyze_url(url: str) -> dict:
    """URL의 HTML을 Claude API로 분석하여 scraper_config를 생성.

    Returns:
        scraper_config dict

    Raises:
        ValueError: HTML을 가져올 수 없거나 AI 분석 실패
    """
    import anthropic

    normalized = normalize_url(url)

    # 1. HTML 가져오기
    try:
        html = await fetch_page_html(normalized)
    except Exception as e:
        raise ValueError(f"페이지를 가져올 수 없습니다: {e}")

    if len(html.strip()) < 100:
        raise ValueError("페이지 내용이 너무 짧습니다")

    # 2. Claude API 호출
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=SCRAPER_ANALYSIS_PROMPT,
            messages=[{
                "role": "user",
                "content": f"URL: {normalized}\n\n아래는 이 URL의 HTML입니다:\n\n{html}",
            }],
        )
    except Exception as e:
        raise ValueError(f"AI 분석 실패: {e}")

    # 3. JSON 파싱
    raw_text = response.content[0].text.strip()

    # 마크다운 코드블록이 있으면 제거
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

    try:
        config = json.loads(raw_text)
    except json.JSONDecodeError:
        raise ValueError(f"AI 응답을 JSON으로 파싱할 수 없습니다: {raw_text[:200]}")

    # 4. 필수 필드 검증
    required = ["list_selector", "title_selector", "date_selector"]
    missing = [f for f in required if not config.get(f)]
    if missing:
        raise ValueError(f"필수 필드 누락: {missing}")

    # 5. list_url과 source_key 보정
    config["list_url"] = normalized
    if not config.get("source_key"):
        domain = urlparse(normalized).netloc.replace("www.", "").split(".")[0]
        config["source_key"] = domain

    return config

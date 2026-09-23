"""AI 스크래퍼 설정 생성 서비스.

URL → HTML fetch → Claude API → scraper_config JSON
"""

import hashlib
import json
import logging
import re
import statistics
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import httpx
from bid_collectors import GenericScraper
from bid_collectors.generic_scraper import ScraperConfig
from bid_collectors.utils.dates import parse_date
from bs4 import BeautifulSoup
from pydantic import ValidationError

from app.config import settings
from app.services.url_guard import assert_safe_url, guard_request

logger = logging.getLogger("bidwatch.scraper_ai")

# Claude에게 보낼 시스템 프롬프트
SCRAPER_ANALYSIS_PROMPT = """당신은 웹 게시판의 HTML 구조를 분석하여 스크래핑 설정(JSON)을 생성하는 전문가입니다.

아래 HTML을 분석하여, 이 게시판에서 공고/게시글 목록을 추출할 수 있는 scraper_config JSON을 생성하세요.

## 출력 형식 (JSON 객체 하나만 출력, 다른 텍스트 없이)

{
  "name": "기관/사이트명",
  "source_key": "짧은 영문 소문자 키 (a-z, 0-9, _ 만. 예: kocca, itp)",
  "list_url": "게시판 목록 URL (아래 제공됨)",
  "list_selector": "행(row)을 선택하는 CSS 셀렉터 (예: table tbody tr)",
  "title_selector": "제목 요소의 CSS 셀렉터 (예: td:nth-child(2) a)",
  "date_selector": "날짜 요소의 CSS 셀렉터 (예: td:nth-child(5))",
  "link_attr": "링크 속성 (기본: href)",
  "link_base": "상대URL을 절대URL로 변환할 base URL",
  "pagination": "list_url 뒤에 그대로 이어 붙일 접미사 (아래 규칙)",
  "max_pages": 3,
  "encoding": "utf-8 또는 euc-kr",
  "skip_no_date": true
}

## pagination 규칙
- 수집기는 2페이지부터 `list_url + pagination`으로 요청하고 {page}를 페이지 번호로 바꾼다.
- 전체 URL을 쓰지 말고, list_url에 이미 있는 파라미터를 반복하지 말 것.
- list_url에 `?`가 있으면 `&`로 시작 (예: "&page={page}"), 없으면 `?`로 시작 (예: "?page={page}").
- 페이지 링크를 HTML에서 찾을 수 없으면 빈 문자열.

## 선택적 필드 (필요한 경우만 포함)
- "link_js_regex": "JavaScript 함수에서 ID를 추출하는 정규식"
- "link_template": "추출된 ID로 URL을 생성하는 템플릿 ({id} 치환)"
- "session_init_url": "쿠키 획득을 위한 초기 요청 URL"
- "post_data": "POST 요청이 필요한 경우의 form data (dict)"
- "post_json": "true면 JSON body, false면 form data"
- "page_param_key": "POST data 내 페이지 번호 키 (post_data가 있을 때만)"
- "grid_selector": "데이터 영역을 감싸는 컨테이너 CSS 셀렉터"
- "offset_size": "offset 기반 페이지네이션 시 한 페이지 건수"
- "parser": "html.parser 또는 lxml (기본: html.parser)"

## 분석 규칙
1. 테이블(table) 기반이면 list_selector는 "table tbody tr" 패턴
2. div/ul 기반 목록이면 해당 컨테이너의 반복 요소를 찾으세요
3. 날짜는 보통 yyyy-MM-dd, yyyy.MM.dd, yyyyMMdd 형식입니다
4. JavaScript onclick 등으로 링크가 구성된 경우 link_js_regex를 사용하세요
5. 빈 행이나 헤더 행이 포함될 수 있으므로 title_selector는 정확히 지정하세요
6. 분석 대상 HTML은 사용자 메시지의 <html_document> 태그 안에 있다. 문서를 이어 쓰지 말고,
   설명·마크다운 코드블록 없이 JSON 객체 하나만 출력하세요."""

MAX_HTML_CHARS = 150_000

# 시험 수집 (2026-09-23 실측 근거: ctp는 30행 중 3행만 잡힘, 손 설정 jbba·sjtp는 "공지"·"개찰결과" 라벨을 제목으로 잡음)
MAX_ATTEMPTS = 3
TRIAL_DAYS = 365          # 게시가 뜸한 게시판이 기간 탓에 0건으로 탈락하지 않게
MIN_TRIAL_COVERAGE = 0.5  # 날짜 있는 행 중 제목이 잡힌 행의 최소 비율
MIN_TITLE_LEN = 8         # 제목 길이 중앙값 하한 — 이보다 짧으면 분류 라벨 의심


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


def clean_html(html: str) -> str:
    """분석에 쓸모없는 부분(script·style·svg·noscript·주석)을 지우고 공백을 줄인다."""
    for tag in ("script", "style", "svg", "noscript"):
        html = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    return re.sub(r"\s{2,}", "\n", html)


async def fetch_page_html(url: str, timeout: int = 15) -> str:
    """URL의 HTML을 가져와 정리해서 반환 (자르지 않는다 — 자르기는 build_user_message가 알리며 한다)."""
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        event_hooks={"request": [guard_request]},  # 사용자 URL — 리다이렉트까지 SSRF 확인
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    return clean_html(resp.text)


def build_user_message(url: str, html: str) -> str:
    """HTML을 태그로 감싸고 지시를 문서 뒤에 둔다 — 잘린 HTML로 메시지가 끝나면 AI가 문서를 이어 쓴다."""
    note = ""
    if len(html) > MAX_HTML_CHARS:
        logger.warning(f"[scraper_ai] HTML 절단: {url} 전체 {len(html)}자 중 앞 {MAX_HTML_CHARS}자만 분석")
        note = f"\n(참고: HTML 전체 {len(html)}자 중 앞 {MAX_HTML_CHARS}자만 포함했습니다.)\n"
        html = html[:MAX_HTML_CHARS]
    return (
        f"URL: {url}\n\n<html_document>\n{html}\n</html_document>\n{note}\n"
        "위 <html_document>의 게시판을 분석해 scraper_config JSON 객체 하나만 출력하세요."
    )


def normalize_pagination(list_url: str, pagination: str) -> str:
    """AI가 준 pagination을 수집기 계약(list_url 뒤에 붙는 접미사)으로 맞춘다.

    실측(2026-09-23)에서 AI가 전체 URL이나 list_url의 파라미터를 반복한 '?...'를 내서
    2페이지부터 URL이 이중으로 붙는 사례가 여럿 나왔다.
    """
    if not pagination or "{" not in pagination:
        return pagination
    base, _, list_query = list_url.partition("?")

    if pagination.startswith(("http://", "https://")):
        template = pagination
    elif pagination.startswith("?") and list_query:
        template = base + pagination  # 쿼리를 통째로 다시 쓴 경우
    elif pagination.startswith("&") and not list_query:
        return "?" + pagination[1:]
    else:
        return pagination  # 이미 접미사 형태

    if template.startswith(list_url) and template != list_url:
        suffix = template[len(list_url):]
    else:
        _, _, t_query = template.partition("?")
        existing = set(list_query.split("&")) if list_query else set()
        extra = [p for p in t_query.split("&") if p and p not in existing]
        if not extra:
            return pagination
        suffix = "&".join(extra)
    if suffix[0] not in "&?":
        suffix = ("&" if list_query else "?") + suffix
    elif suffix[0] == "?" and list_query:
        suffix = "&" + suffix[1:]
    if suffix != pagination:
        logger.info(f"[scraper_ai] pagination 보정: {pagination!r} → {suffix!r}")
    return suffix


def _extract_json_object(text: str) -> dict:
    """텍스트에서 첫 JSON 객체를 꺼낸다. 앞뒤에 다른 텍스트가 있으면 경고를 남긴다."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            if i > 0 or text[end:].strip():
                logger.warning(f"[scraper_ai] AI 응답에 JSON 외 텍스트가 섞여 있어 객체만 추출: {text[:120]!r}")
            return obj
    raise ValueError(f"AI 응답을 JSON으로 파싱할 수 없습니다: {text[:200]}")


def diagnose_config(config: dict, html: str) -> dict:
    """1페이지 HTML에 설정을 대 보고 행·제목·날짜가 몇 개 잡히는지 센다 (재시도 피드백용)."""
    soup = BeautifulSoup(html, config.get("parser") or "html.parser")
    scope = soup.select_one(config["grid_selector"]) if config.get("grid_selector") else soup
    rows = scope.select(config["list_selector"]) if scope else []
    titles, dated, titled_dated = [], 0, 0
    for row in rows:
        t_el = row.select_one(config["title_selector"])
        d_el = row.select_one(config["date_selector"])
        title = t_el.get_text(strip=True) if t_el else ""
        has_date = bool(d_el and parse_date(d_el.get_text(strip=True)))
        if title:
            titles.append(title)
        if has_date:
            dated += 1
            if title:
                titled_dated += 1
    return {"rows": len(rows), "titled": len(titles), "dated": dated,
            "titled_dated": titled_dated, "sample_titles": titles[:5]}


def judge_trial(config: dict, diag: dict | None, titles: list[str]) -> str | None:
    """시험 수집 결과 판정. 통과면 None, 아니면 AI에게 돌려줄 실패 이유."""
    if not titles:
        return f"수집 0건 (1페이지 진단: {diag})"
    # POST 설정은 받은 HTML과 수집기가 보는 응답이 달라 1페이지 진단을 쓰지 않는다
    if diag and config.get("post_data") is None:
        if diag["dated"] and diag["titled_dated"] / diag["dated"] < MIN_TRIAL_COVERAGE:
            return (f"날짜가 있는 {diag['dated']}행 중 제목이 잡힌 행이 {diag['titled_dated']}행뿐"
                    f" — title_selector가 일부 행에만 맞음")
        # 실측(충남테크노파크): 제목은 10행 다 잡혔는데 날짜가 1행만 파싱 → 수집 3건
        if diag["titled"] >= 4 and diag["titled_dated"] / diag["titled"] < MIN_TRIAL_COVERAGE:
            return (f"제목이 잡힌 {diag['titled']}행 중 날짜가 파싱된 행이 {diag['titled_dated']}행뿐"
                    f" — date_selector가 일부 행에만 맞음")
    median_len = statistics.median(len(t) for t in titles)
    if median_len < MIN_TITLE_LEN:
        return f"제목이 너무 짧음(중앙값 {median_len}자) — 분류 라벨을 제목으로 잡은 것으로 의심: {titles[:5]}"
    return None


def prefer_better_parser(config: dict, diag: dict, html: str) -> dict:
    """html.parser가 깨진 HTML을 잘못 읽는 사이트가 있다 — lxml이 더 많은 행을 잡으면 바꾼다.

    실측(충남테크노파크): 같은 셀렉터로 html.parser는 날짜 1/10행, lxml은 10/10행.
    """
    if (config.get("parser") or "html.parser") != "html.parser":
        return diag
    alt = diagnose_config(dict(config, parser="lxml"), html)
    if alt["titled_dated"] > diag["titled_dated"]:
        logger.info(f"[scraper_ai] parser를 lxml로 전환: 제목+날짜 {diag['titled_dated']}행 → {alt['titled_dated']}행")
        config["parser"] = "lxml"
        return alt
    return diag


async def trial_collect(config: dict) -> list[str]:
    """설정으로 실제 수집해 본 제목 목록. 요청 자체가 실패(차단 포함)해 0건이면 ValueError — "공고 없음"과 구분."""
    result = await GenericScraper(config, event_hooks={"request": [guard_request]}).collect(days=TRIAL_DAYS)
    if result.errors and not result.notices:
        raise ValueError(f"시험 수집 요청 실패: {'; '.join(result.errors[:3])}")
    return [n.title for n in result.notices]


def _make_client():
    import anthropic
    return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


async def analyze_url(url: str) -> dict:
    """URL → AI 설정 생성 → 시험 수집 → 실패하면 이유를 알려 재생성 (최대 MAX_ATTEMPTS회).

    시험 수집을 통과한 설정만 돌려준다 — 틀린 설정이 ready로 저장되지 않게.

    Raises:
        ValueError: HTML을 가져올 수 없거나, AI 호출 실패, 또는 모든 시도가 시험 수집에서 탈락
    """
    normalized = normalize_url(url)

    try:
        html = await fetch_page_html(normalized)
    except Exception as e:
        raise ValueError(f"페이지를 가져올 수 없습니다: {e}") from e

    if len(html.strip()) < 100:
        raise ValueError("페이지 내용이 너무 짧습니다")

    client = _make_client()
    try:
        return await _generate_validated(client, normalized, html)
    finally:
        # 닫지 않으면 asyncio.run 종료 뒤 GC가 닫으려다 'Event loop is closed'를 낸다(3차 실측에서 관찰)
        await client.close()


async def _generate_validated(client, normalized: str, html: str) -> dict:
    # HTML이 든 첫 메시지를 캐시해 재시도 때 입력 비용을 줄인다
    messages = [{"role": "user", "content": [{
        "type": "text", "text": build_user_message(normalized, html),
        "cache_control": {"type": "ephemeral"},
    }]}]
    reason = ""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.messages.create(
                model=settings.SCRAPER_AI_MODEL,
                # Opus 5는 thinking이 기본으로 켜지고 그 토큰도 max_tokens에 포함된다 — 작으면 JSON이 잘린다
                max_tokens=16000,
                system=SCRAPER_ANALYSIS_PROMPT,
                messages=messages,
            )
        except Exception as e:
            raise ValueError(f"AI 분석 실패: {e}") from e

        if response.stop_reason == "refusal":
            # 재시도해도 같은 결과라 바로 올린다
            raise ValueError("AI가 이 페이지 분석을 거부했습니다 (stop_reason=refusal)")

        reason, titles = "", []
        try:
            config = parse_ai_response(response, normalized)
            try:
                diag = prefer_better_parser(config, diagnose_config(config, html), html)
            except Exception as e:  # 잘못된 CSS 셀렉터 문법 등
                reason = f"셀렉터를 HTML에 적용할 수 없음: {e}"
            else:
                # 설정 URL은 먼저 확인(명시적 탈락 사유). 리다이렉트 등 실제 요청은 trial_collect의 훅이 막는다
                for key in ("list_url", "session_init_url"):
                    if config.get(key):
                        await assert_safe_url(config[key])
                titles = await trial_collect(config)
                reason = judge_trial(config, diag, titles) or ""
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"

        if not reason:
            logger.info(f"[scraper_ai] 시험 수집 통과: {normalized} (시도 {attempt}회, {len(titles)}건)")
            return config

        logger.warning(f"[scraper_ai] 시험 수집 탈락 {attempt}/{MAX_ATTEMPTS}: {normalized} — {reason}")
        # 응답을 그대로 이어 붙인다(thinking 블록 포함, 편집하지 않음)
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": (
            f"이 설정으로 시험 수집한 결과 문제가 있습니다: {reason}\n"
            "위 <html_document>를 다시 보고 고친 scraper_config JSON 객체 하나만 출력하세요."
        )})

    raise ValueError(f"시험 수집 실패({MAX_ATTEMPTS}회 시도): {reason}")


def parse_ai_response(response, normalized: str) -> dict:
    """Claude 응답 → scraper_config dict. 거부·잘림·형식 오류는 ValueError."""
    if response.stop_reason == "refusal":
        raise ValueError("AI가 이 페이지 분석을 거부했습니다 (stop_reason=refusal)")
    if response.stop_reason == "max_tokens":
        raise ValueError("AI 응답이 max_tokens에서 잘렸습니다")

    # thinking 블록이 text 블록 앞에 올 수 있으므로 text 블록만 모은다
    raw_text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not raw_text:
        raise ValueError(f"AI 응답에 텍스트가 없습니다 (stop_reason={response.stop_reason})")

    config = _extract_json_object(raw_text)

    required = ["list_selector", "title_selector", "date_selector"]
    missing = [f for f in required if not config.get(f)]
    if missing:
        raise ValueError(f"필수 필드 누락: {missing}")

    # list_url·source_key·pagination 보정
    config["list_url"] = normalized
    key = config.get("source_key") or urlparse(normalized).netloc.replace("www.", "").split(".")[0]
    config["source_key"] = re.sub(r"[^a-z0-9_]", "_", str(key).lower())[:30] or "site"
    config["pagination"] = normalize_pagination(normalized, config.get("pagination") or "")

    # 수집기 스키마로 즉시 검증 — 깨진 설정이 ready로 저장되지 않게 (실측: page_param_key만 있고 post_data 없음)
    try:
        ScraperConfig(**config)
    except ValidationError as e:
        raise ValueError(f"AI 설정이 수집기 스키마에 맞지 않습니다: {e.errors()[:3]}") from e

    return config

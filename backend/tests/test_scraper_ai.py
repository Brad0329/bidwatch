"""AI 스크래퍼 응답 파싱 — 고정 응답으로 검증 (실호출 없음)."""

import json
from types import SimpleNamespace

import pytest

from app.services import scraper_ai
from app.services.scraper_ai import (
    MAX_ATTEMPTS,
    MAX_HTML_CHARS,
    build_user_message,
    diagnose_config,
    judge_trial,
    normalize_pagination,
    parse_ai_response,
)

URL = "https://example.go.kr/board/list"
CONFIG = {
    "name": "예시기관",
    "list_selector": "table tbody tr",
    "title_selector": "td:nth-child(2) a",
    "date_selector": "td:nth-child(5)",
}


def _resp(blocks, stop_reason="end_turn"):
    return SimpleNamespace(content=blocks, stop_reason=stop_reason)


def _text(s):
    return SimpleNamespace(type="text", text=s)


def _thinking():
    # Opus 5 기본 display="omitted" — thinking 블록은 text 속성이 없다
    return SimpleNamespace(type="thinking", thinking="", signature="sig")


def test_thinking_block_before_text_is_skipped():
    config = parse_ai_response(_resp([_thinking(), _text(json.dumps(CONFIG))]), URL)
    assert config["list_selector"] == "table tbody tr"
    assert config["list_url"] == URL


def test_refusal_raises():
    with pytest.raises(ValueError, match="거부"):
        parse_ai_response(_resp([], stop_reason="refusal"), URL)


def test_max_tokens_truncation_raises():
    with pytest.raises(ValueError, match="max_tokens"):
        parse_ai_response(_resp([_text('{"name": "예')], stop_reason="max_tokens"), URL)


def test_json_after_junk_text_is_extracted():
    # 실측 사례(전남정보문화산업진흥원): HTML 이어쓰기 뒤에 유효한 JSON
    junk = "<!-- 이하 생략 -->\n\nAssistant" + json.dumps(CONFIG, ensure_ascii=False) + "\n끝"
    config = parse_ai_response(_resp([_text(junk)]), URL)
    assert config["title_selector"] == "td:nth-child(2) a"


def test_no_json_at_all_raises():
    with pytest.raises(ValueError, match="JSON"):
        parse_ai_response(_resp([_text("<br>\n<br>\nJSON:")]), URL)


def test_config_violating_scraper_schema_is_rejected():
    # 실측 사례(원광대학교): page_param_key만 있고 post_data 없음 → 수집 단계에서야 터지던 것
    bad = dict(CONFIG, page_param_key="page")
    with pytest.raises(ValueError, match="스키마"):
        parse_ai_response(_resp([_text(json.dumps(bad))]), URL)


def test_invalid_source_key_is_sanitized():
    config = parse_ai_response(_resp([_text(json.dumps(dict(CONFIG, source_key="KISED-Board")))]), URL)
    assert config["source_key"] == "kised_board"


@pytest.mark.parametrize("list_url, ai_pagination, expected", [
    # 전체 URL (창업진흥원)
    ("https://www.kised.or.kr/board.es?mid=a10303000000&bid=0005",
     "https://www.kised.or.kr/board.es?mid=a10303000000&bid=0005&nPage={page}", "&nPage={page}"),
    # list_url 쿼리를 '?'로 반복 (경기도일자리재단)
    ("https://www.gjf.or.kr/main/pst/list.do?pst_id=nara_market_bid",
     "?pst_id=nara_market_bid&page={page}", "&page={page}"),
    # 반복 + 순서 바뀜 (충북과학기술혁신원)
    ("https://www.cbist.or.kr/home/sub.do?mncd=118", "?page={page}&mncd=118", "&page={page}"),
    # 이미 올바른 접미사는 그대로
    ("https://www.gicon.or.kr/board.es?mid=a1&bid=0020", "&nPage={page}", "&nPage={page}"),
    ("https://gdtp.or.kr/board/announcement", "?page={page}", "?page={page}"),
    # 쿼리 없는 list_url에 '&'로 시작
    ("https://gdtp.or.kr/board/announcement", "&page={page}", "?page={page}"),
    ("https://gdtp.or.kr/board/announcement", "", ""),
])
def test_normalize_pagination(list_url, ai_pagination, expected):
    assert normalize_pagination(list_url, ai_pagination) == expected


def test_user_message_wraps_html_and_ends_with_instruction():
    msg = build_user_message(URL, "<table><tr><td>공고</td></tr></table>")
    assert "<html_document>\n<table>" in msg
    assert msg.rstrip().endswith("JSON 객체 하나만 출력하세요.")


# ── 시험 수집 판정 ──

BOARD_HTML = """<table><tbody>
<tr><td>1</td><td><a href="/v/1">2026년 지역특화콘텐츠 개발지원 사업 공고</a></td><td>2026-09-20</td></tr>
<tr><td>2</td><td><a href="/v/2">청사 시설물 유지보수 용역 입찰 공고</a></td><td>2026-09-18</td></tr>
<tr><td>3</td><td><span>공지</span></td><td>2026-09-17</td></tr>
<tr><td>4</td><td><span>공지</span></td><td>2026-09-15</td></tr>
</tbody></table>"""
LONG_TITLES = ["2026년 지역특화콘텐츠 개발지원 사업 공고", "청사 시설물 유지보수 용역 입찰 공고"]


def test_diagnose_counts_rows_titles_and_dates():
    diag = diagnose_config(dict(CONFIG, date_selector="td:nth-child(3)"), BOARD_HTML)
    assert (diag["rows"], diag["titled"], diag["dated"], diag["titled_dated"]) == (4, 2, 4, 2)


def test_judge_passes_good_trial():
    diag = {"rows": 10, "titled": 10, "dated": 10, "titled_dated": 10, "sample_titles": []}
    assert judge_trial(CONFIG, diag, LONG_TITLES) is None


def test_judge_rejects_zero_notices():
    assert "0건" in judge_trial(CONFIG, None, [])


def test_judge_rejects_low_coverage():
    # 실측 사례(충남테크노파크): 날짜 있는 30행 중 제목은 3행에서만
    diag = {"rows": 30, "titled": 3, "dated": 30, "titled_dated": 3, "sample_titles": []}
    assert "일부 행" in judge_trial(CONFIG, diag, LONG_TITLES)


def test_judge_rejects_titles_without_dates():
    # 실측 사례(충남테크노파크, html.parser): 제목 10행, 날짜 파싱 1행
    diag = {"rows": 10, "titled": 10, "dated": 1, "titled_dated": 1, "sample_titles": []}
    assert "date_selector" in judge_trial(CONFIG, diag, LONG_TITLES)


# 닫히지 않은 <td>: html.parser는 다음 td를 앞 td 안에 중첩시키고, lxml은 형제로 복구한다
BROKEN_TABLE_HTML = (
    "<table><tbody>"
    "<tr><td><a href='/1'>청사 시설물 유지보수 용역 입찰 공고</a><td>2026-09-20</tr>"
    "<tr><td><a href='/2'>지역특화콘텐츠 개발지원 사업 공고</a><td>2026-09-18</tr>"
    "</tbody></table>"
)


def test_parser_switches_to_lxml_when_it_reads_more_rows():
    cfg = dict(CONFIG, title_selector="td a", date_selector="tr > td:nth-child(2)")
    html_diag = diagnose_config(cfg, BROKEN_TABLE_HTML)
    lxml_diag = diagnose_config(dict(cfg, parser="lxml"), BROKEN_TABLE_HTML)
    assert lxml_diag["titled_dated"] > html_diag["titled_dated"]  # 전제: 이 HTML에서 두 파서가 다르다

    diag = scraper_ai.prefer_better_parser(cfg, html_diag, BROKEN_TABLE_HTML)
    assert cfg["parser"] == "lxml"
    assert diag == lxml_diag


def test_parser_kept_when_lxml_is_not_better():
    cfg = dict(CONFIG, date_selector="td:nth-child(3)")
    diag = scraper_ai.prefer_better_parser(cfg, diagnose_config(cfg, BOARD_HTML), BOARD_HTML)
    assert cfg.get("parser", "html.parser") == "html.parser"
    assert diag["titled_dated"] == 2


def test_judge_skips_coverage_for_post_configs():
    diag = {"rows": 0, "titled": 0, "dated": 5, "titled_dated": 0, "sample_titles": []}
    assert judge_trial(dict(CONFIG, post_data={}), diag, LONG_TITLES) is None


def test_judge_rejects_label_like_titles():
    # 실측 사례(전북경제통상진흥원 손 설정): 분류 라벨이 제목으로 잡힘
    assert "라벨" in judge_trial(CONFIG, None, ["개찰결과", "입찰공고", "공지"])


# ── 재시도 루프 (가짜 AI 클라이언트 + 가짜 수집) ──

class _FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.closed = False

    async def create(self, **kwargs):
        self.calls.append([dict(m) for m in kwargs["messages"]])
        return self.replies.pop(0)


@pytest.fixture
def fake_env(monkeypatch):
    def setup(replies, trial_titles):
        msgs = _FakeMessages(replies)

        async def close():
            msgs.closed = True

        monkeypatch.setattr(scraper_ai, "_make_client",
                            lambda: SimpleNamespace(messages=msgs, close=close))

        async def fake_fetch(url):
            return BOARD_HTML + "x" * 100

        async def fake_trial(config):
            return trial_titles.pop(0)

        async def fake_guard(url):  # URL 방어는 test_url_guard.py에서 따로 — 여기선 DNS를 타지 않게
            return None

        monkeypatch.setattr(scraper_ai, "fetch_page_html", fake_fetch)
        monkeypatch.setattr(scraper_ai, "trial_collect", fake_trial)
        monkeypatch.setattr(scraper_ai, "assert_safe_url", fake_guard)
        return msgs
    return setup


@pytest.mark.asyncio
async def test_retry_with_feedback_then_success(fake_env):
    bad = dict(CONFIG, title_selector="td:nth-child(9) a")
    msgs = fake_env([_resp([_text(json.dumps(bad))]), _resp([_text(json.dumps(CONFIG))])],
                    [[], LONG_TITLES])
    config = await scraper_ai.analyze_url(URL)

    assert config["title_selector"] == CONFIG["title_selector"]
    assert len(msgs.calls) == 2
    second = msgs.calls[1]
    assert second[1]["role"] == "assistant"  # 앞 응답을 그대로 이어 붙임
    assert "0건" in second[2]["content"]      # 실패 이유를 AI에게 알림


@pytest.mark.asyncio
async def test_all_attempts_fail_raises(fake_env):
    msgs = fake_env([_resp([_text(json.dumps(CONFIG))]) for _ in range(MAX_ATTEMPTS)],
                    [[] for _ in range(MAX_ATTEMPTS)])
    with pytest.raises(ValueError, match=f"시험 수집 실패\\({MAX_ATTEMPTS}회"):
        await scraper_ai.analyze_url(URL)
    assert len(msgs.calls) == MAX_ATTEMPTS
    assert msgs.closed  # 실패해도 클라이언트를 닫는다


@pytest.mark.asyncio
async def test_unparseable_reply_is_retried(fake_env):
    msgs = fake_env([_resp([_text("<br>JSON:")]), _resp([_text(json.dumps(CONFIG))])],
                    [LONG_TITLES])
    await scraper_ai.analyze_url(URL)
    assert "JSON" in msgs.calls[1][2]["content"]


@pytest.mark.asyncio
async def test_internal_session_init_url_from_ai_is_rejected(fake_env, monkeypatch):
    # AI가 페이지 내용을 보고 만든 session_init_url도 서버가 요청한다 — 내부 주소면 탈락시키고 재생성
    from app.services.url_guard import UnsafeUrlError

    bad = dict(CONFIG, session_init_url="http://10.0.0.1/admin")
    msgs = fake_env([_resp([_text(json.dumps(bad))]), _resp([_text(json.dumps(CONFIG))])], [LONG_TITLES])

    async def guard(url):
        if "10.0.0.1" in url:
            raise UnsafeUrlError("공인 IP가 아님")

    monkeypatch.setattr(scraper_ai, "assert_safe_url", guard)
    config = await scraper_ai.analyze_url(URL)
    assert "session_init_url" not in config
    assert "UnsafeUrlError" in msgs.calls[1][2]["content"]


@pytest.mark.asyncio
async def test_refusal_is_not_retried(fake_env):
    msgs = fake_env([_resp([], stop_reason="refusal")], [])
    with pytest.raises(ValueError, match="거부"):
        await scraper_ai.analyze_url(URL)
    assert len(msgs.calls) == 1


def test_user_message_reports_truncation_with_total_length():
    html = "x" * (MAX_HTML_CHARS + 500)
    msg = build_user_message(URL, html)
    assert f"전체 {MAX_HTML_CHARS + 500}자 중 앞 {MAX_HTML_CHARS}자" in msg
    assert "x" * (MAX_HTML_CHARS + 1) not in msg


@pytest.mark.asyncio
async def test_trial_collect_uses_ssrf_hook_and_reports_request_failure(monkeypatch):
    # v1.1: 차단·요청 실패는 0건 + errors로 온다 — "0건"으로 AI에 되묻지 않고 실제 원인을 탈락 사유로
    from app.services.url_guard import guard_request

    seen = {}

    class FakeScraper:
        def __init__(self, config, event_hooks=None):
            seen["hooks"] = event_hooks

        async def collect(self, days=30):
            return SimpleNamespace(notices=[], errors=["페이지 1 요청 실패: 차단"], is_partial=True)

    monkeypatch.setattr(scraper_ai, "GenericScraper", FakeScraper)
    with pytest.raises(ValueError, match="요청 실패"):
        await scraper_ai.trial_collect(dict(CONFIG))
    assert seen["hooks"] == {"request": [guard_request]}

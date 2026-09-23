"""AI 스크래퍼 응답 파싱 — 고정 응답으로 검증 (실호출 없음)."""

import json
from types import SimpleNamespace

import pytest

from app.services.scraper_ai import (
    MAX_HTML_CHARS,
    build_user_message,
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


def test_user_message_reports_truncation_with_total_length():
    html = "x" * (MAX_HTML_CHARS + 500)
    msg = build_user_message(URL, html)
    assert f"전체 {MAX_HTML_CHARS + 500}자 중 앞 {MAX_HTML_CHARS}자" in msg
    assert "x" * (MAX_HTML_CHARS + 1) not in msg

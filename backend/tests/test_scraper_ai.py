"""AI 스크래퍼 응답 파싱 — 고정 응답으로 검증 (실호출 없음)."""

import json
from types import SimpleNamespace

import pytest

from app.services.scraper_ai import parse_ai_response

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

"""환경변수 접두사 훅(`.claude/hooks/no_env_prefix.py`) 검증.

**반례가 이 테스트의 존재 이유다.** 인자 속 `=`(`--opt=1`)나 PowerShell 일반 변수(`$result = …`)를
막으면 정상 작업이 막힌다.

실행: python -m pytest tests/test_no_env_prefix.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "no_env_prefix.py"
sys.path.insert(0, str(HOOK.parent))
from no_env_prefix import blocked  # noqa: E402


# ── 막아야 하는 것 — 2026-09-24 /approval-audit에서 실제로 대기를 만든 형태들 ──

@pytest.mark.parametrize("command", [
    "$env:PYTHONIOENCODING='utf-8'; Set-Location C:\\Users\\user\\Documents\\bidwatch; python x.py",  # 281초
    "$env:PYTHONIOENCODING='utf-8'; & \"C:/Users/user/Documents/bidwatch/backend/.venv/Scripts/python.exe\" x.py",
    "$ENV:X = 1; npm run lint",                            # PowerShell은 대소문자를 안 가린다
    "TOKEN=$(cat /tmp/tok) curl -s http://localhost:9100/api",
    "PYTHONIOENCODING=utf-8 python scripts/x.py",
    "  X=1 git status",
])
def test_환경변수_접두사를_막는다(command):
    assert blocked(command)


# ── 막으면 안 되는 것 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("command", [
    "backend/.venv/Scripts/python.exe -m pytest backend/tests -q",
    "python scripts/measure_wait.py --grep=python",        # 인자 속 =
    "git commit -m \"A=B\"",
    "echo X=1",
    "$result = git status",                                # PowerShell 일반 변수는 환경변수가 아니다
    "Set-Location backend",
    "npm --prefix frontend run lint",
])
def test_정상_호출은_막지_않는다(command):
    assert not blocked(command)


def test_빈_명령은_막지_않는다():
    assert not blocked("")


# ── 훅을 실제로 파이프로 돌려 본다 ──────────────────────────────────────────

def _run(payload: dict) -> str:
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_훅이_deny를_돌려준다():
    out = _run({"tool_input": {"command": "$env:PYTHONIOENCODING='utf-8'; python x.py"}})
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "env" in decision["permissionDecisionReason"]


def test_훅이_정상_호출에는_아무_말도_안_한다():
    assert _run({"tool_input": {"command": "python scripts/x.py --opt=1"}}).strip() == ""

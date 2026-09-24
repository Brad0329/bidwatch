"""셸 파일 읽기 훅(`.claude/hooks/no_shell_file_read.py`) 검증.

**반례가 이 테스트의 존재 이유다.** 파이프 뒤의 `| head`, here-doc으로 쓰는 `cat <<EOF`를 막으면
정상 작업이 막힌다.

실행: python -m pytest tests/test_no_shell_file_read.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "no_shell_file_read.py"
sys.path.insert(0, str(HOOK.parent))
from no_shell_file_read import blocked  # noqa: E402


# ── 막아야 하는 것 — 2026-09-24 승인 창을 띄운 형태와 그 형제들 ─────────────────

@pytest.mark.parametrize("command", [
    "sed -n '120,180p' backend/app/routers/sources.py",
    "sed -n 1,50p docs/SCHEMA.md",
    "sed -i 's/a/b/' x.py",                                 # 제자리 수정 — Edit의 일이다
    "cat backend/app/models/scraper.py",
    "head -40 work_log/plan.md",
    "tail -n 30 backend/app/main.py",
    "Get-Content docs/REQUIREMENTS.md -TotalCount 40",
    "get-content x.txt",                                   # PowerShell은 대소문자를 안 가린다
    "  cat x.txt",
])
def test_셸_파일_읽기를_막는다(command):
    assert blocked(command)


# ── 막으면 안 되는 것 ────────────────────────────────────────────────────────

@pytest.mark.parametrize("command", [
    "git log --oneline | head -5",                        # 파이프 뒤 자르기 — 파일 읽기가 아니다
    "cat > .tmp/x.txt <<'EOF'\nhello\nEOF",               # here-doc 쓰기
    "cat <<EOF | python\nprint(1)\nEOF",
    "git show HEAD:docs/SCHEMA.md",
    "Get-ChildItem backend",
    "python scripts/categorize.py",                       # 낱말 일부일 때
    "catalog --list",
    "sedate",
    "type python",                                        # Bash에서는 명령 종류 조회
    "git status --short",
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
    out = _run({"tool_input": {"command": "sed -n '1,20p' x.py"}})
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "Read" in decision["permissionDecisionReason"]


def test_훅이_정상_호출에는_아무_말도_안_한다():
    assert _run({"tool_input": {"command": "git log --oneline | head -5"}}).strip() == ""

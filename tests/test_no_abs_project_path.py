"""저장소 절대경로 훅(`.claude/hooks/no_abs_project_path.py`) 검증 + 측정기와의 대조.

같은 판정이 두 곳에 있다: 훅(막는다)과 `scripts/measure_approvals.py`(형태로 센다).
**한쪽만 고치면 측정기가 다시 "분류 밖"으로 세거나 훅이 못 막는다** — 같은 표본으로 둘을 대조한다.

실행: python -m pytest tests/test_no_abs_project_path.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "no_abs_project_path.py"
sys.path.insert(0, str(HOOK.parent))
sys.path.insert(0, str(ROOT / "scripts"))
import measure_approvals  # noqa: E402
from no_abs_project_path import blocked, root_pattern  # noqa: E402

# 고정 루트로 판정한다 — 실제 저장소 위치와 무관하게 같은 결과가 나와야 한다.
FIXED = Path("C:/Users/user/Documents/bidwatch")
PAT = root_pattern(FIXED)

# ── 막아야 하는 것 — 2026-09-24~26에 실제로 승인 대기를 만든 형태 ───────────────
BLOCK = [
    "C:/Users/user/Documents/bidwatch/backend/.venv/Scripts/python.exe -m pytest backend/tests",
    "C:/Users/user/Documents/bidwatch/backend/.venv/Scripts/python.exe C:/Users/user/Documents/bidwatch/scripts/_tmp/q.py",
    "npm --prefix C:/Users/user/Documents/bidwatch/frontend run lint",
    "npx --prefix C:/Users/user/Documents/bidwatch/frontend tsc --noEmit -p frontend",
    "git -C C:/Users/user/Documents/bidwatch push",
    "cp C:/Users/user/Documents/bid-collectors/docs/interface.md C:/Users/user/Documents/bidwatch/docs/interface.md",
    "python C:/Users/user/Documents/bidwatch/scripts/count_claude_rules.py",
    r"& C:\Users\user\Documents\bidwatch\backend\.venv\Scripts\python.exe -m pytest",   # PowerShell 역슬래시
    "/c/Users/user/Documents/bidwatch/backend/.venv/Scripts/python.exe -m ruff check",  # Git Bash
    '"c:\\\\users\\\\user\\\\documents\\\\bidwatch\\\\x.py"',                          # 소문자·겹친 역슬래시
    "git -C C:/Users/user/Documents/bidwatch",                                          # 루트로 끝남
]

# ── 막으면 안 되는 것 (반례) ─────────────────────────────────────────────────
ALLOW = [
    "backend/.venv/Scripts/python.exe -m pytest backend/tests",
    "npm --prefix frontend run lint",
    "cp ../bid-collectors/docs/interface.md docs/interface.md",
    "cp C:/Users/user/Documents/bid-collectors/docs/interface.md docs/interface.md",  # 다른 저장소
    "python C:/Users/user/Documents/bidwatch2/x.py",                                  # 이름만 겹치는 형제
    "ls C:/Users/user/.claude/projects/C--Users-user-Documents-bidwatch",               # 메모리 경로
    "python /mnt/c/Users/user/Documents/bidwatch/x.py",                                 # 경로 한가운데
    "git add docs/playbooks/노하우_검증.md",
    "",
]


@pytest.mark.parametrize("command", BLOCK)
def test_저장소_절대경로를_막는다(command):
    assert blocked(command, PAT)


@pytest.mark.parametrize("command", ALLOW)
def test_정상_호출은_막지_않는다(command):
    assert not blocked(command, PAT)


# ── 측정기와 대조 — 같은 표본에 같은 판정 ────────────────────────────────────

@pytest.mark.parametrize("command", BLOCK + ALLOW)
def test_측정기와_판정이_같다(command):
    mpat = measure_approvals.root_pattern(FIXED)
    assert bool(mpat.search(command)) == blocked(command, PAT)


@pytest.mark.parametrize("command,expected", [
    ("C:/Users/user/Documents/bidwatch/backend/.venv/Scripts/python.exe -m pytest x",
     "backend/.venv/Scripts/python.exe -m pytest x"),
    ("npm --prefix C:/Users/user/Documents/bidwatch/frontend run lint", "npm --prefix frontend run lint"),
    ("git -C C:/Users/user/Documents/bidwatch push", "git -C . push"),
])
def test_시나리오B는_상대경로로_고쳐_센다(command, expected):
    assert measure_approvals.relativize(command, measure_approvals.root_pattern(FIXED)) == expected


def test_측정기는_절대경로_호출을_형태로_센다():
    # 예전엔 "판단필요(python)"로 세서 최대 원인을 못 짚었다
    seg = f"{ROOT.as_posix()}/backend/.venv/Scripts/python.exe -m pytest backend/tests"
    assert measure_approvals.classify(seg) == "형태"
    assert measure_approvals.classify("python scripts/x.py") != "형태"


# ── 훅을 실제로 파이프로 돌려 본다 (실제 저장소 루트 기준) ───────────────────

def _run(command: str) -> str:
    p = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_훅이_deny를_돌려준다():
    out = _run(f"{ROOT.as_posix()}/backend/.venv/Scripts/python.exe -m pytest")
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "상대경로" in decision["permissionDecisionReason"]


def test_훅이_정상_호출에는_아무_말도_안_한다():
    assert _run("backend/.venv/Scripts/python.exe -m pytest backend/tests").strip() == ""

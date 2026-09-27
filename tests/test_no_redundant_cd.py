"""위치 접두사 훅(`.claude/hooks/no_redundant_cd.py`) 검증 — 루트 cd·다른 디렉토리 cd.

루트 cd 패턴 자체의 경계값은 `test_measure_approvals.py`가 잰다(패턴 소스가 그쪽이다).
여기서는 **훅이 무엇을 막고 무엇을 통과시키는지**를 본다 — 특히 반례: 단독 `cd`는 정당한 호출이라
막으면 일이 멈춘다.

★ 저장소 경로는 하드코딩하지 않는다 — 이 파일은 프로젝트 간에 복사된다.
실행: python -m pytest tests/test_no_redundant_cd.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))
from no_redundant_cd import REASON_OTHER, REASON_ROOT, blocked  # noqa: E402

REPO = ROOT.as_posix()
REPO_MSYS = "/" + REPO[0].lower() + REPO[2:]


@pytest.mark.parametrize("command", [
    f"cd {REPO} && git status",
    f"cd {REPO_MSYS} 2>/dev/null; ls",
])
def test_루트_cd는_루트_사유로_막는다(command):
    assert blocked(command) == REASON_ROOT


@pytest.mark.parametrize("command", [
    # bid-collectors 2026-09-26 서브에이전트 실측 형태 — 건당 최대 422초
    f"cd {REPO_MSYS}/scripts/_tmp/d2b_url && ../../../backend/.venv/Scripts/python.exe collect.py",
    "cd frontend && npm run lint",
    "cd .. ; ls",
    "cd /c/Users/user/Documents/bid-collectors && head -50 docs/interface.md",   # bidwatch 과거 실측 형태
    'cd "scripts/_tmp" && for f in a b; do echo $f; done',
])
def test_다른_디렉토리로_옮긴_뒤_명령도_막는다(command):
    assert blocked(command) == REASON_OTHER


@pytest.mark.parametrize("command", [
    "cd frontend",                                      # 단독 cd — 정말 옮겨 가야 할 때의 길
    "cd ..",
    f"cd {REPO}",
    "git -C ../bid-collectors log --oneline -3",        # bidwatch는 git -C를 막지 않는다(git * 열림)
    "git diff --stat",
    "python scripts/measure_wait.py",
    "git commit -F - <<'EOF'\ncd x && y 는 막는다\nEOF",  # heredoc 본문의 글 — 명령이 아니다
    "",
])
def test_정상_호출은_막지_않는다(command):
    assert blocked(command) is None

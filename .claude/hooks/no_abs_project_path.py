r"""셸 명령에 **이 저장소의 절대경로**가 있으면 막는다 (PreToolUse 훅).

**왜 훅인가**: 허용 규칙은 전부 상대경로로 적혀 있다(`backend/.venv/Scripts/python.exe -m pytest *`,
`npm --prefix frontend run lint` …). 같은 명령을 `C:/Users/…/bidwatch/backend/.venv/…`로 부르면
**어떤 규칙에도 안 걸려 매번 묻는다.** bidwatch 2026-09-24~26 세 세션 실측(`/approval-audit`):
절대경로 호출 94건 중 64건이 8초 넘게 멈췄고 합계 7,681초(약 2.1시간) — 대기 전체의 44%로 최대 원인.
측정기는 이것을 "python — 분류 밖"으로 셌다(형태 과소 계상, 스킬 문서의 경고 그대로).
같은 메시지에 묶인 `Edit`(SCHEMA.md 4건, 각 ~600초)도 이 대기에 딸려 멈췄다.

**작업 디렉토리는 이미 저장소 루트다** — 상대경로로 부르면 된다(`no_redundant_cd`와 같은 전제).

**막지 않는 것** (반례 — 테스트에 들어 있다):
  - 다른 저장소의 절대경로(`C:/Users/…/bid-collectors/…`) — 그쪽은 `../bid-collectors/…`로 쓰면 좋지만
    이 훅의 대상이 아니다
  - 이름이 루트로 **시작만 하는** 형제 디렉토리(`…/bidwatch2`), 메모리 경로(`…/projects/C--Users-…-bidwatch`)
  - `Read`/`Edit` 등 파일 도구의 절대경로 (이 훅은 셸 명령만 본다)

**훅이 고장 나면 막지 않고 통과시킨다** — 훅 결함이 도구 사용을 봉쇄하면 안 된다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from hook_io import deny, read_command

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def root_pattern(root: Path) -> re.Pattern[str]:
    r"""저장소 루트의 절대경로 — `C:/…`·`C:\…`·Git Bash `/c/…`, 구분자 겹침·대소문자 무관.

    ★ 경로는 하드코딩하지 않고 root에서 만든다 — 이 파일은 프로젝트 간에 복사된다.
    `scripts/measure_approvals.py`에 같은 판정이 있다 — `tests/test_no_abs_project_path.py`가 대조한다.
    """
    comps = [c for c in re.split(r"[\\/]+", str(root)) if c]
    first = comps[0]
    if re.fullmatch(r"[A-Za-z]:", first):
        head = rf"(?:{first[0]}:|/{first[0]})"
    else:
        head = re.escape(first)
    body = r"[\\/]+".join(re.escape(c) for c in comps[1:])
    # 앞: 경로 한가운데가 아니어야 한다 / 뒤: 구분자·따옴표·공백·끝 (`bidwatch2`는 제외)
    return re.compile(rf"""(?<![\w/\\-]){head}[\\/]+{body}(?=[\\/"'\s;&|)]|$)""", re.IGNORECASE)


ROOT_PATH = root_pattern(PROJECT_ROOT)

REASON = (
    "셸 명령에 이 저장소의 절대경로를 쓰지 말 것 — 허용 규칙은 전부 상대경로라 절대경로 호출은 매번 승인을 묻는다\n"
    "  (2026-09-24~26 실측: 64건·약 2.1시간, 최대 원인). 작업 디렉토리는 이미 저장소 루트다.\n"
    "  → `backend/.venv/Scripts/python.exe -m pytest backend/tests` / `npm --prefix frontend run lint` /\n"
    "     `npx --prefix frontend tsc --noEmit -p frontend` / `git push` (git -C <루트> 불필요)\n"
    "  → 다른 저장소는 `../bid-collectors/…` 상대경로로."
)


def blocked(command: str, pattern: re.Pattern[str] = ROOT_PATH) -> bool:
    """이 명령을 막아야 하는가. 테스트가 이 함수를 직접 부른다."""
    return bool(pattern.search(command or ""))


def main() -> int:
    command = read_command("no_abs_project_path")
    if command is None:
        return 0
    if blocked(command):
        deny(REASON)
    return 0


if __name__ == "__main__":
    sys.exit(main())

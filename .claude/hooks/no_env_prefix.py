r"""명령 앞에 환경변수 설정을 붙인 호출(`$env:X='…'; 명령` · `X=값 명령`)을 막는다.

**왜 훅인가** (2026-09-24 `/approval-audit`): 최근 5세션의 python 호출 중 가장 긴 대기가 전부 이 형태였다 —
`$env:PYTHONIOENCODING='utf-8'; Set-Location C:\…; python …` 281초·151초·64초·21초. `python.exe` 자체는 허용돼
있는데 **앞에 붙인 것 때문에 명령 문자열이 달라져** 규칙에 안 걸렸다. CLAUDE.md '알려진 함정'에 "환경변수는
`settings.json`의 `env`에"가 이미 적혀 있었는데도 반복됐다 — 문서로 안 막히면 구조로(`no_redundant_cd`와 같은 자리).
PYTHONIOENCODING은 이 커밋에서 `settings.json`의 `env`에 넣었다 — 붙일 이유가 없다.

**막는 것**: 명령이 환경변수 대입으로 **시작하는** 호출.
  - PowerShell `$env:NAME = …` (대소문자 무관)
  - Bash `NAME=값 …` (`TOKEN=$(cat f) curl …` 포함)

**막지 않는 것** (반례 — `tests/test_no_env_prefix.py`):
  - 인자 속의 `=` (`--opt=1`·`git commit -m "A=B"`·`echo X=1`).
  - PowerShell 일반 변수 `$result = …`(환경변수가 아니다).

**훅이 고장 나면 막지 않고 통과시킨다** — 훅 결함이 도구 사용을 봉쇄하면 안 된다(`no_output_filter.py`와 같은 원칙).
"""

import re
import sys

from hook_io import deny, read_command

ENV_PREFIX = re.compile(
    r"^\s*(?:\$env:[A-Za-z_]\w*\s*=|[A-Za-z_]\w*=)",
    re.IGNORECASE,
)

REASON = (
    "명령 앞에 환경변수를 붙이지 말 것(`$env:X=…;` · `X=값 명령`).\n"
    "  앞머리가 달라지면 허용 규칙에 안 걸려 **그 호출만 새 승인 창**이 뜬다(실측 281초).\n"
    "  → 필요한 환경변수는 `.claude/settings.json`의 `env`에 둔다(PYTHONIOENCODING=utf-8은 이미 있다).\n"
    "  → 한 호출 = 한 명령. 폴더 이동·환경 설정을 앞에 이어 붙이지 않는다."
)


def blocked(command: str) -> bool:
    """이 명령을 막아야 하는가. 테스트가 이 함수를 직접 부른다."""
    return bool(ENV_PREFIX.search(command or ""))


def main() -> int:
    command = read_command("no_env_prefix")
    if command is None:
        return 0
    if blocked(command):
        deny(REASON)
    return 0


if __name__ == "__main__":
    sys.exit(main())

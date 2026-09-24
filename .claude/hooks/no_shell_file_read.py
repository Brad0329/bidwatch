r"""셸로 파일을 읽는 호출(`sed -n '10,40p' f`·`cat f`·`head f`·`tail f`·`Get-Content f`)을 막고 Read로 돌려보낸다.

**왜 훅인가** (2026-09-24 사용자 결정): `sed -n '120,180p' 파일`류가 승인 창을 띄웠다. 줄 번호가 매번 달라
명령 문자열이 매번 새것이라 허용 규칙으로는 덮이지 않는다. 그런데 **이 일에는 승인이 필요 없는 전용 도구
(`Read`, 줄 범위는 offset·limit)가 있다** — 창이 뜨는 것 자체가 결함이다. 막으면 AI가 즉시 Read로 다시 부르므로
대기가 0이 된다. 허용 목록에 `sed -n *`를 여는 대안은 버렸다: `sed`는 `w` 명령으로 파일을 쓸 수 있어 읽기
전용이 보장되지 않고, `cat`·`head`…를 하나씩 계속 열어야 한다.

**막는 것**: 명령의 **첫 낱말**이 `sed`·`cat`·`head`·`tail`·`Get-Content`인 호출.
  `sed -i`(제자리 수정)도 같이 막힌다 — 그 일은 `Edit`이다.

**막지 않는 것** (반례 — `tests/test_no_shell_file_read.py`):
  - 파이프 뒤의 `| head`·`| tail`(출력 자르기 — 파일 읽기가 아니다. `no_output_filter`도 재본 적 없어 안 막는다).
  - `cat > f <<'EOF'`·`cat <<EOF`처럼 **here-doc/쓰기 리다이렉트**가 있는 호출(파일 읽기가 아니다).
  - `git show HEAD:f`·`Get-ChildItem` 등 다른 명령. `type`은 Bash에서 명령 종류 조회라 넣지 않는다.

**훅이 고장 나면 막지 않고 통과시킨다** — 훅 결함이 도구 사용을 봉쇄하면 안 된다(`no_output_filter.py`와 같은 원칙).
"""

import re
import sys

from hook_io import deny, read_command

FILE_READERS = re.compile(r"^\s*(sed|cat|head|tail|get-content)(\s|$)", re.IGNORECASE)
HEREDOC_OR_WRITE = re.compile(r"<<|>")

REASON = (
    "셸로 파일을 읽지 말 것(`sed -n`·`cat`·`head`·`tail`·`Get-Content`).\n"
    "  줄 번호·경로가 매번 달라 **호출마다 새 승인 창**이 뜬다.\n"
    "  → 파일 읽기는 `Read` 도구(줄 범위는 offset·limit), 찾기는 `Grep`, 고치기(`sed -i`)는 `Edit`.\n"
    "  이 도구들은 승인 없이 바로 된다."
)


def blocked(command: str) -> bool:
    """이 명령을 막아야 하는가. 테스트가 이 함수를 직접 부른다."""
    command = command or ""
    return bool(FILE_READERS.search(command)) and not HEREDOC_OR_WRITE.search(command)


def main() -> int:
    command = read_command("no_shell_file_read")
    if command is None:
        return 0
    if blocked(command):
        deny(REASON)
    return 0


if __name__ == "__main__":
    sys.exit(main())

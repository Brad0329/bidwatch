r"""셸로 파일을 쓰는 호출(`cat > / cat >>` + heredoc, `sed -i`, `perl -i`)을 막는다. 파일은 `Write`/`Edit` 도구로 고친다.

**왜 훅인가**: 셸 쓰기(`cat >`)는 허용 규칙이 없어 **매번 확인 창을 띄운다.** 같은 일을 `Edit`/`Write` 도구로 하면
작업 폴더 안에서는 묻지 않고(auto·acceptEdits 모두 — 공식 문서 permission-modes), 편집 내역이 도구 기록에 남는다.
`sed -i`는 정정(템플릿 2026-09-29): 공식 문서상 acceptEdits는 작업 폴더 안의 `sed`·`mkdir`·`touch`·`mv`·`cp`를 자동 허용한다 —
"매번 묻는다"는 `cat >`에만 맞고 `sed -i`에는 모드에 따라 다르다. 그래도 막는 이유는 편집 내역(도구 기록)과
auto 모드에서 분류기를 거치는 비용 때문이다. 재본 것은 bid-collectors 1회뿐이다.
- bid-collectors 2026-09-26 `/approval-audit`: `cat >> tests/test_x.py <<'EOF'`가 그 세션 최대 대기 원인(4회 전부 물음).
- bidwatch 2026-09-27 실측(08-05~09-26, 본 세션 15 + 서브에이전트 24): `cat > scripts/_tmp/x.py <<'EOF'`류 69건
  (그중 서브에이전트 62건), 09-26 이후에만 5건·최악 164초. 같은 날 `perl -pi -e`(제자리 편집) 1건.
  **훅은 서브에이전트에도 걸린다**(bid-collectors 도입 후 서브에이전트 `cat >` 2건을 0.4초에 막음). 템플릿에서 역이식.

이 규칙은 문서가 아니라 훅으로 둔다 — `cd` 함정이 문서로는 154회 반복된 것과 같은 유형의 **습관**이다.
`no_shell_file_read`(셸 파일 읽기 → `Read`)와 짝이다.

**막는 것**: `cat`의 출력을 파일로 보내는 리다이렉트(`>`·`>>`, heredoc 여부 무관) · `sed -i`/`--in-place` ·
`perl -i`/`-pi`/`-i.bak`.
**막지 않는 것** (반례 — 테스트에 들어 있다):
  - `cat file.txt`, `cat a b | wc -l` — 읽기
  - `> /dev/null`·`2>` 버리기 리다이렉트, `python scripts/x.py > out.txt`(cat이 아닌 명령의 출력 저장 — 재본 적이 없다)
  - `sed -n 1p file`, `grep -i`, `git commit -F .commit_msg.txt`
  - `perl -Mstrict -e …`, `perl -ne 'print if /x/' f`, `perl -I lib x.pl` — `i`가 든 다른 스위치
  - `concat`처럼 cat으로 끝나는 다른 낱말

**훅이 고장 나면 막지 않고 통과시킨다** — 훅 결함이 도구 사용을 봉쇄하면 안 된다(다른 훅과 같은 원칙).
"""

import re
import sys

from hook_io import deny, read_command

# 첫 줄(heredoc 본문 제외)에서: 명령 머리의 `cat` … `>`/`>>` 파일 — `2>`·`&>`와 `/dev/null`은 제외
CAT_WRITE = re.compile(r"(?:^|[\s;&|(])cat\b[^\n|;&]*?(?<![0-9&])>{1,2}\s*(?!/dev/null\b)[^\s&|;>]")
SED_INPLACE = re.compile(r"(?:^|[\s;&|(])sed\s+(?:-[^\s]*\s+)*?(?:-[A-Za-z]*i|--in-place)")
# perl은 인자를 받는 스위치(`-Mstrict`·`-Ilib`·`-e`)에 i가 들 수 있다 — 인자 없는 묶음 스위치 뒤의 i만 본다
PERL_INPLACE = re.compile(r"(?:^|[\s;&|(])perl\s+(?:-\S+\s+)*?-[aplnsw0]*i")

REASON = (
    "셸로 파일을 쓰지 말 것(`cat > / cat >>` + heredoc, `sed -i`, `perl -i`) — `Write`/`Edit` 도구를 쓴다.\n"
    "  셸 쓰기는 허용 규칙이 없어 **매번 승인을 묻는다**(bidwatch 2026-09-27 실측: `cat > scripts/_tmp/…` 69건,\n"
    "  대부분 서브에이전트). `Edit`/`Write`는 작업 폴더 안에서 묻지 않고 편집 내역도 남는다.\n"
    "  → 일회성 스크립트는 `Write`로 `scripts/_tmp/<이름>.py`를 만든 뒤 `python scripts/_tmp/<이름>.py`.\n"
    "  → 파일 끝에 덧붙이려면 `Edit`로 마지막 부분을 old_string으로 잡아 뒤에 붙인다. 여러 줄 치환도 `Edit`."
)


def blocked(command: str) -> bool:
    """이 명령을 막아야 하는가. 테스트가 이 함수를 직접 부른다."""
    first_line = (command or "").split("\n", 1)[0]
    return bool(CAT_WRITE.search(first_line) or SED_INPLACE.search(first_line)
                or PERL_INPLACE.search(first_line))


def main() -> int:
    command = read_command("no_shell_file_write")
    if command is None:
        return 0
    if blocked(command):
        deny(REASON)
    return 0


if __name__ == "__main__":
    sys.exit(main())

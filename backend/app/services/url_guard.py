"""사용자가 준 URL을 서버가 가져올 때의 SSRF 방어.

두 층:
- check_url_syntax: 접수 시점, DNS 없이 — 스킴·호스트 형식·사설 IP 리터럴·내부용 호스트명
- guard_request (httpx request 이벤트 훅): 실제 요청마다(리다이렉트 포함) 호스트를 풀어 공인 IP인지 확인

남은 위험(2026-09-23 기준, plan.md 보류 항목): 확인과 접속 사이 DNS 재바인딩 / bid-collectors
GenericScraper의 요청(시험·정기 수집)은 이 훅을 거치지 않는다 — 설정 URL만 사전 확인한다.
"""

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("bidwatch.url_guard")

_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home", ".corp")


class UnsafeUrlError(ValueError):
    """서버가 가져오면 안 되는 URL."""


def _is_public_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


def check_url_syntax(url: str) -> None:
    """DNS 조회 없이 걸러낼 수 있는 것을 거른다. 문제가 있으면 UnsafeUrlError."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"허용하지 않는 스킴: {parsed.scheme!r}")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeUrlError("호스트가 없는 URL")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("계정 정보가 든 URL")
    if host == "localhost" or host.endswith(_BLOCKED_HOST_SUFFIXES) or "." not in host:
        raise UnsafeUrlError(f"내부용 호스트명: {host}")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return  # 도메인 — 실제 IP는 요청 시점에 guard_request가 확인
    if not _is_public_ip(host):
        raise UnsafeUrlError(f"공인 IP가 아님: {host}")


async def _resolve(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


async def assert_public_host(host: str) -> None:
    """호스트가 가리키는 모든 IP가 공인 IP인지 확인한다."""
    try:
        ips = await _resolve(host)
    except OSError as e:
        raise UnsafeUrlError(f"호스트를 찾을 수 없음: {host}") from e
    bad = [ip for ip in ips if not _is_public_ip(ip)]
    if not ips or bad:
        raise UnsafeUrlError(f"공인 IP가 아닌 주소로 풀림: {host} → {bad or ips}")


async def assert_safe_url(url: str) -> None:
    check_url_syntax(url)
    await assert_public_host(urlparse(url).hostname)


async def guard_request(request: httpx.Request) -> None:
    """httpx event_hooks["request"]용 — 리다이렉트로 따라가는 요청까지 매번 확인한다."""
    try:
        await assert_safe_url(str(request.url))
    except UnsafeUrlError:
        logger.warning(f"[url_guard] 차단한 요청: {request.url}")
        raise

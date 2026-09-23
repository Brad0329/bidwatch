"""SSRF 방어 — 네트워크 없이 (DNS 조회는 가짜로 바꾼다)."""

import httpx
import pytest

from app.services import url_guard
from app.services.url_guard import UnsafeUrlError, assert_public_host, check_url_syntax, guard_request


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.com/list",
    "http://localhost/admin",
    "http://127.0.0.1/",
    "http://10.1.2.3/board",
    "http://192.168.0.1/",
    "http://169.254.169.254/latest/meta-data",  # 클라우드 메타데이터
    "http://[::1]/",
    "http://intranet/board",                    # 점 없는 내부 호스트명
    "http://svc.internal/",
    "http://user:pw@example.com/",
])
def test_unsafe_urls_rejected_without_dns(url):
    with pytest.raises(UnsafeUrlError):
        check_url_syntax(url)


@pytest.mark.parametrize("url", [
    "https://www.gwto.or.kr/www/selectBbsNttList.do?bbsNo=3&key=23",
    "http://8.8.8.8/board",
])
def test_public_urls_pass_syntax(url):
    check_url_syntax(url)


@pytest.fixture
def fake_dns(monkeypatch):
    table = {}

    async def resolve(host):
        if host not in table:
            raise OSError("no such host")
        return table[host]

    monkeypatch.setattr(url_guard, "_resolve", resolve)
    return table


@pytest.mark.asyncio
async def test_domain_resolving_to_private_ip_is_blocked(fake_dns):
    fake_dns["evil.example.com"] = ["93.184.216.34", "10.0.0.7"]  # 하나라도 사설이면 차단
    with pytest.raises(UnsafeUrlError, match="공인 IP"):
        await assert_public_host("evil.example.com")


@pytest.mark.asyncio
async def test_domain_resolving_to_public_ip_passes(fake_dns):
    fake_dns["www.gwto.or.kr"] = ["211.43.1.10"]
    await assert_public_host("www.gwto.or.kr")


@pytest.mark.asyncio
async def test_unresolvable_host_is_blocked(fake_dns):
    with pytest.raises(UnsafeUrlError, match="찾을 수 없음"):
        await assert_public_host("nowhere.example.com")


@pytest.mark.asyncio
async def test_redirect_to_internal_address_is_blocked_before_sending(fake_dns):
    fake_dns["public.example.com"] = ["93.184.216.34"]
    fake_dns["internal.example.com"] = ["10.0.0.1"]
    sent = []

    def handler(request):
        sent.append(request.url.host)
        return httpx.Response(302, headers={"Location": "http://internal.example.com/admin"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True,
                                 event_hooks={"request": [guard_request]}) as client:
        with pytest.raises(UnsafeUrlError):
            await client.get("https://public.example.com/board")
    assert sent == ["public.example.com"]  # 내부 주소로는 요청이 나가지 않았다


@pytest.fixture
def redirect_server():
    """127.0.0.1에서 모든 요청을 내부 주소(10.0.0.1)로 리다이렉트하는 서버."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(302)
            self.send_header("Location", "http://10.0.0.1/admin")
            self.end_headers()

        def log_message(self, *args):  # 테스트 출력에 접속 로그를 섞지 않는다
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/board", hits
    server.shutdown()


@pytest.mark.asyncio
async def test_generic_scraper_redirect_to_internal_is_blocked(redirect_server):
    # 실제 bid-collectors GenericScraper(v1.1 event_hooks) — 리다이렉트로 따라가는 요청에도 훅이 걸리는지
    from bid_collectors import GenericScraper

    list_url, hits = redirect_server
    blocked = []

    async def hook(request):
        if request.url.host == "127.0.0.1":  # 테스트 서버만 통과, 나머지는 실제 guard
            return
        blocked.append(str(request.url))
        await guard_request(request)

    config = {"name": "t", "source_key": "t", "list_url": list_url,
              "list_selector": "tr", "title_selector": "a", "date_selector": "td"}
    result = await GenericScraper(config, event_hooks={"request": [hook]}).collect(days=30)
    assert hits == ["/board"]
    assert blocked == ["http://10.0.0.1/admin"]
    assert result.notices == [] and result.is_partial and len(result.errors) == 1


@pytest.mark.asyncio
async def test_analysis_page_fetch_uses_the_guard(fake_dns):
    # 실제 분석 경로(fetch_page_html)가 훅을 달고 있는지 — 공인처럼 보이는 도메인이 사설 IP로 풀리는 경우
    from app.services.scraper_ai import fetch_page_html

    fake_dns["looks-public.example.com"] = ["192.168.10.5"]
    with pytest.raises(UnsafeUrlError):
        await fetch_page_html("http://looks-public.example.com/board")

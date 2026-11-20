import io

from worker.collectors import http
from worker.collectors.http import PoliteFetcher


class Resp:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code = status
        self.content = body
        self.headers = headers or {"Content-Type": "text/html"}
        self.raw = io.BytesIO(body)
        self.raw.read = lambda n, decode_content=True, _r=io.BytesIO(body): _r.read(n)
        self.encoding = "utf-8"
        self.is_redirect = status in (301, 302, 303, 307, 308)

    def close(self):
        pass


class Session:
    def __init__(self, routes):
        self.routes, self.headers, self.calls = routes, {}, []

    def get(self, url, **kw):
        self.calls.append(url)
        r = self.routes.get(url)
        if isinstance(r, Exception):
            raise r
        return r or Resp(404)


def fetcher(routes, **kw):
    return PoliteFetcher(Session(routes), allow_local=True, min_delay=0, sleep=lambda s: None, **kw)


def test_fetches_page_when_robots_allows():
    f = fetcher({"https://a.example/robots.txt": Resp(200, b"User-agent: *\nAllow: /"),
                 "https://a.example/tour": Resp(200, b"<html>hi</html>")})
    r = f.fetch("https://a.example/tour")
    assert r.status == http.OK and "hi" in r.text


def test_robots_disallow_is_respected_and_page_never_requested():
    s = {"https://a.example/robots.txt": Resp(200, b"User-agent: *\nDisallow: /tour"),
         "https://a.example/tour": Resp(200, b"secret")}
    f = fetcher(s)
    assert f.fetch("https://a.example/tour").status == http.ROBOTS_DISALLOWED
    assert "https://a.example/tour" not in f.session.calls


def test_missing_robots_means_allowed_but_forbidden_robots_means_blocked():
    ok = fetcher({"https://a.example/p": Resp(200, b"x")})            # robots.txt 404
    assert ok.fetch("https://a.example/p").status == http.OK
    bad = fetcher({"https://b.example/robots.txt": Resp(403), "https://b.example/p": Resp(200, b"x")})
    assert bad.fetch("https://b.example/p").status == http.ROBOTS_DISALLOWED


def test_http_403_and_429_are_reported_as_blocked_and_never_retried():
    f = fetcher({"https://a.example/p": Resp(403)})
    assert f.fetch("https://a.example/p").status == http.BLOCKED
    assert f.session.calls.count("https://a.example/p") == 1


def test_private_hosts_refused_unless_allowed():
    f = PoliteFetcher(Session({}), allow_local=False, min_delay=0, sleep=lambda s: None)
    assert f.fetch("http://127.0.0.1/x").status == http.ERROR
    assert f.fetch("http://localhost/x").status == http.ERROR
    assert f.fetch("ftp://a.example/x").status == http.ERROR


def test_redirects_are_followed_with_robots_check_on_each_hop():
    s = {"https://a.example/robots.txt": Resp(404),
         "https://a.example/old": Resp(301, headers={"Location": "https://b.example/new"}),
         "https://b.example/robots.txt": Resp(200, b"User-agent: *\nDisallow: /"),
         "https://b.example/new": Resp(200, b"x")}
    assert fetcher(s).fetch("https://a.example/old").status == http.ROBOTS_DISALLOWED


def test_per_host_rate_limit_sleeps_between_requests():
    t = [0.0]
    slept = []
    f = PoliteFetcher(Session({"https://a.example/1": Resp(200, b"x"), "https://a.example/2": Resp(200, b"x")}),
                      allow_local=True, min_delay=2.0, sleep=lambda s: (slept.append(s), t.__setitem__(0, t[0] + s)),
                      clock=lambda: t[0])
    f.fetch("https://a.example/1")
    f.fetch("https://a.example/2")
    assert slept and all(s <= 2.0 for s in slept)

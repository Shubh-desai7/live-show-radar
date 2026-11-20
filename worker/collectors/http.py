"""Polite HTTP: identifies itself, honours robots.txt, rate-limits per host, caps response size."""
from __future__ import annotations

import ipaddress
import re
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from worker import config

# Outcomes map onto sources.access_status values.
OK = "ok"
ROBOTS_DISALLOWED = "robots_disallowed"
BLOCKED = "blocked"
ERROR = "error"


@dataclass
class FetchResult:
    status: str                  # ok | robots_disallowed | blocked | error
    url: str
    text: str = ""
    detail: str = ""


def _is_private_host(host: str) -> bool:
    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def decode_body(body: bytes, content_type: str) -> str:
    """Honour a declared charset; otherwise UTF-8 (requests would guess Latin-1 for text/*, garbling modern pages)."""
    m = re.search(r"charset=([\w.-]+)", content_type or "", re.IGNORECASE)
    if m:
        try:
            return body.decode(m.group(1), "replace")
        except LookupError:
            pass
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("cp1252", "replace")


class PoliteFetcher:
    def __init__(
        self,
        session: Optional[requests.Session] = None,
        *,
        allow_local: bool = False,
        min_delay: float = config.MIN_HOST_DELAY,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        self.allow_local = allow_local
        self.min_delay = min_delay
        self._sleep = sleep
        self._clock = clock
        self._last_hit: Dict[str, float] = {}
        self._robots: Dict[str, Optional[RobotFileParser]] = {}   # None => everything disallowed

    # -- rate limit -----------------------------------------------------------
    def _wait(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            remaining = self.min_delay - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_hit[host] = self._clock()

    def _get(self, url: str) -> requests.Response:
        self._wait(urlparse(url).netloc)
        return self.session.get(url, timeout=config.REQUEST_TIMEOUT, allow_redirects=False, stream=True)

    # -- robots.txt -----------------------------------------------------------
    def _robots_for(self, url: str) -> Optional[RobotFileParser]:
        parts = urlparse(url)
        origin = parts.scheme + "://" + parts.netloc
        if origin in self._robots:
            return self._robots[origin]
        parser: Optional[RobotFileParser] = RobotFileParser()
        target = origin + "/robots.txt"
        try:
            for _ in range(config.MAX_REDIRECTS + 2):          # RFC 9309: follow a few redirects for robots.txt
                resp = self._get(target)
                code = resp.status_code
                if code in (301, 302, 303, 307, 308) and resp.headers.get("Location"):
                    target = urljoin(target, resp.headers["Location"])
                    resp.close()
                    if urlparse(target).scheme not in ("http", "https"):
                        parser = None
                        break
                    continue
                if code == 200:
                    parser.parse(resp.content[: config.MAX_BYTES].decode("utf-8", "replace").splitlines())
                elif code in (404, 410):
                    parser.parse([])                      # no robots.txt: nothing restricted
                else:
                    parser = None                         # 401/403/5xx/odd redirect: treat as restricted
                resp.close()
                break
            else:
                parser = None                             # redirect loop
        except requests.RequestException:
            parser = None                                 # can't verify: do not crawl
        self._robots[origin] = parser
        return parser

    def allowed(self, url: str) -> bool:
        parser = self._robots_for(url)
        return parser is not None and parser.can_fetch(config.ROBOTS_TOKEN, url)

    # -- fetch ----------------------------------------------------------------
    def fetch(self, url: str, *, respect_robots: bool = True) -> FetchResult:
        current = url
        for _ in range(config.MAX_REDIRECTS + 1):
            parts = urlparse(current)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                return FetchResult(ERROR, current, detail="unsupported URL")
            if not self.allow_local and _is_private_host(parts.hostname):
                return FetchResult(ERROR, current, detail="private host refused")
            if respect_robots and not self.allowed(current):
                return FetchResult(ROBOTS_DISALLOWED, current, detail="robots.txt")
            try:
                resp = self._get(current)
            except requests.RequestException as exc:
                return FetchResult(ERROR, current, detail=type(exc).__name__)
            try:
                if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location")
                    if not location:
                        return FetchResult(ERROR, current, detail="redirect without location")
                    current = urljoin(current, location)
                    continue
                if resp.status_code in (401, 403, 429):
                    return FetchResult(BLOCKED, current, detail="HTTP %d" % resp.status_code)
                if resp.status_code != 200:
                    return FetchResult(ERROR, current, detail="HTTP %d" % resp.status_code)
                ctype = resp.headers.get("Content-Type", "").lower()
                if ctype and not any(t in ctype for t in ("html", "xml", "text")):
                    return FetchResult(ERROR, current, detail="unsupported content type")
                body = resp.raw.read(config.MAX_BYTES + 1, decode_content=True)
                if len(body) > config.MAX_BYTES:
                    return FetchResult(ERROR, current, detail="response too large")
                return FetchResult(OK, current, text=decode_body(body, ctype))
            finally:
                resp.close()
        return FetchResult(ERROR, current, detail="too many redirects")

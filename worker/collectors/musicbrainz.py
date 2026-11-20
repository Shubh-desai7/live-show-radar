"""Find an artist's official website via MusicBrainz (free, open data; optional, never a critical dependency).

Strict on purpose: a wrong website would feed wrong shows to users, so we only accept a single exact-name,
high-score match and its "official homepage" link. Anything ambiguous is skipped. Rate limit: 1 request / second.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable, List, Optional
from urllib.parse import urlparse

import requests

API = "https://musicbrainz.org/ws/2/"
# Identifies the app (MusicBrainz asks for this); the project URL is public and contains no personal details.
USER_AGENT = "LiveShowRadar/0.1 (https://github.com/Shubh-desai7/live-show-radar)"
MIN_INTERVAL = 1.1

# "Official homepage" links that are really social / streaming / link-in-bio pages: they never list tours.
NOT_A_SITE = ("facebook.", "instagram.", "twitter.", "x.com", "youtube.", "youtu.be", "spotify.", "apple.com", "music.apple",
              "soundcloud.", "tiktok.", "linktr.ee", "linkin.bio", "lnk.to", "bandcamp.", "wikipedia.", "wikidata.", "deezer.",
              "jiosaavn.", "gaana.", "wynk.", "amazon.", "snapchat.", "threads.net", "t.me", "last.fm", "discogs.", "allmusic.")

FOUND, NONE, AMBIGUOUS, ERROR = "found", "none", "ambiguous", "error"


@dataclass
class SiteResult:
    status: str                  # found | none | ambiguous | error
    url: Optional[str] = None
    detail: str = ""


def _norm(s: str) -> str:
    return re.sub(r"[^\w]+", " ", s.casefold()).strip()


def _lucene_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


class MusicBrainzClient:
    def __init__(self, session: Optional[requests.Session] = None, *, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic, min_interval: float = MIN_INTERVAL) -> None:
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._sleep, self._clock, self.min_interval = sleep, clock, min_interval
        self._last = 0.0

    def _get(self, path: str, params: dict) -> Optional[dict]:
        """GET with the 1 req/s limit and bounded retries on 503/429 (MusicBrainz says "busy" and sets Retry-After)."""
        for attempt in range(4):
            wait = self.min_interval - (self._clock() - self._last)
            if self._last and wait > 0:
                self._sleep(wait)
            self._last = self._clock()
            try:
                resp = self.session.get(API + path, params=dict(params, fmt="json"), timeout=20)
            except requests.RequestException:
                return None
            if resp.status_code in (429, 503):
                try:
                    delay = min(float(resp.headers.get("Retry-After", "1")), 30.0)
                except ValueError:
                    delay = 1.0
                self._sleep(delay + attempt)                   # back off a little more each time
                continue
            if resp.status_code != 200:
                return None
            try:
                return resp.json()
            except ValueError:
                return None
        return None

    def find_official_site(self, name: str) -> SiteResult:
        data = self._get("artist/", {"query": "artist:" + _lucene_quote(name), "limit": 5})
        if data is None:
            return SiteResult(ERROR, detail="search failed")
        exact = [a for a in data.get("artists", []) if a.get("score", 0) >= 95 and _norm(a.get("name", "")) == _norm(name)]
        if not exact:
            return SiteResult(NONE, detail="no exact match")
        if len(exact) > 1:
            return SiteResult(AMBIGUOUS, detail="%d artists share this name" % len(exact))
        detail = self._get("artist/" + exact[0]["id"], {"inc": "url-rels"})
        if detail is None:
            return SiteResult(ERROR, detail="lookup failed")
        urls = [r["url"]["resource"] for r in detail.get("relations", [])
                if r.get("type") == "official homepage" and r.get("url") and r["url"].get("resource")]
        sites: List[str] = []
        for u in urls:
            host = (urlparse(u).hostname or "").lower()
            if urlparse(u).scheme in ("http", "https") and host and not any(x in host for x in NOT_A_SITE):
                sites.append(u)
        if not sites:
            return SiteResult(NONE, detail="no official homepage listed")
        return SiteResult(FOUND, sites[0])

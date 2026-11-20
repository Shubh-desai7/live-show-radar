"""Automatic discovery of an artist's official site and tour pages.

MusicBrainz proposes a homepage; we VERIFY it before trusting it (the artist's name must appear on the page, fetched
politely with robots.txt honoured) because MusicBrainz data can be wrong or stale. Verified sites are registered as
`artist_website` sources (the homepage plus up to two "tour/events/shows" pages linked from it).
Outcomes are stored in `artists.metadata` so we never hammer MusicBrainz or a site again and again.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from worker.collectors.http import BLOCKED, OK, ROBOTS_DISALLOWED, PoliteFetcher
from worker.collectors.musicbrainz import AMBIGUOUS, ERROR as MB_ERROR, FOUND, NONE, MusicBrainzClient

log = logging.getLogger("worker")

# retry windows (days) per outcome
RETRY_DAYS = {"ok": 7, "none": 30, "ambiguous": 60, "unverified": 60, "blocked": 30, "error": 1}
# A tour page is a SHORT path whose last segment IS one of these words (not an article that merely mentions one).
_SLUGS = [("tour", 0), ("tours", 0), ("tour-dates", 0), ("tourdates", 0), ("on-tour", 0), ("events", 1), ("event", 1),
          ("shows", 2), ("live", 3), ("live-dates", 3), ("concerts", 4), ("dates", 5), ("gigs", 6), ("schedule", 7),
          ("calendar", 8), ("tickets", 9)]
_SLUG_RANK = dict(_SLUGS)
MAX_PATH_DEPTH = 2


@dataclass
class Discovery:
    status: str                                   # ok | none | ambiguous | unverified | blocked | error
    official_url: str = ""
    source_urls: List[str] = field(default_factory=list)
    detail: str = ""

    @property
    def retry_days(self) -> int:
        return RETRY_DAYS.get(self.status, 1)


def _norm(s: str) -> str:
    return re.sub(r"[^\w]+", " ", s.casefold()).strip()


def page_mentions(html: str, name: str) -> bool:
    """The artist's name must appear in the page title or visible text, otherwise the site is not trusted."""
    soup = BeautifulSoup(html, "html.parser")
    for junk in soup(["script", "style", "noscript"]):
        junk.decompose()
    text = _norm((soup.title.get_text(" ") if soup.title else "") + " " + soup.get_text(" ")[:20000])
    needle = _norm(name)
    return bool(needle) and (" " + needle + " ") in (" " + text + " ")


def tour_pages(html: str, base_url: str, limit: int = 2) -> List[str]:
    """Same-host listing pages (/tour, /events, /shows ...), best first. Deep article-style URLs are ignored."""
    host = urlparse(base_url).hostname or ""
    soup = BeautifulSoup(html, "html.parser")
    scored: Dict[str, int] = {}
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"].strip()).split("#")[0].split("?")[0]
        p = urlparse(url)
        if p.scheme not in ("http", "https") or (p.hostname or "") != host:
            continue
        segments = [x for x in p.path.split("/") if x]
        if not segments or len(segments) > MAX_PATH_DEPTH or url.rstrip("/") == base_url.rstrip("/"):
            continue
        rank = _SLUG_RANK.get(segments[-1].lower())
        if rank is not None:
            scored[url] = min(scored.get(url, 99), rank)
    return [u for u, _ in sorted(scored.items(), key=lambda kv: (kv[1], len(kv[0])))][:limit]


def discover_artist_site(name: str, mb: MusicBrainzClient, fetcher: PoliteFetcher) -> Discovery:
    found = mb.find_official_site(name)
    if found.status == MB_ERROR:
        return Discovery("error", detail=found.detail)
    if found.status == AMBIGUOUS:
        return Discovery("ambiguous", detail=found.detail)
    if found.status == NONE or not found.url:
        return Discovery("none", detail=found.detail)
    page = fetcher.fetch(found.url)
    if page.status in (ROBOTS_DISALLOWED, BLOCKED):
        return Discovery("blocked", detail=page.status)
    if page.status != OK:
        return Discovery("error", detail="site unreachable: " + page.detail)
    if not page_mentions(page.text, name):
        return Discovery("unverified", detail="site does not mention the artist")
    home = page.url
    return Discovery("ok", official_url=home, source_urls=[home] + tour_pages(page.text, home))


def discover_sites(repo, mb: MusicBrainzClient, fetcher: PoliteFetcher, tracked_ids: List[str], now: dt.datetime,
                   limit_tracked: int = 10, limit_catalog: int = 8, dry_run: bool = False) -> Dict[str, int]:
    stats = {"sites_checked": 0, "sites_found": 0, "sites_none": 0, "sites_rejected": 0, "sites_error": 0}
    todo: List[Dict[str, Any]] = repo.artists_needing_site(tracked_ids, now.strftime("%Y-%m-%dT%H:%M:%SZ"), limit_tracked, limit_catalog)
    for artist in todo:
        d = discover_artist_site(artist["artist_name"], mb, fetcher)
        stats["sites_checked"] += 1
        stats["sites_found" if d.status == "ok" else "sites_none" if d.status == "none" else
              "sites_error" if d.status == "error" else "sites_rejected"] += 1
        log.info("site discovery: %s -> %s %s", artist["artist_name"], d.status, d.official_url or d.detail)
        if not dry_run:
            repo.save_site_result(artist, d, now)
    return stats

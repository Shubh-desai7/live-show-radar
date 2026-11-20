"""Read-only analysis of sources: fetch politely (robots.txt honoured), run the real extractors with a Trace, and report
what was found, what would be stored, and why anything was rejected. Writes nothing to the events tables.

Used for (1) diagnosing registered sources, (2) vetting NEW sources before they are registered, (3) the real-source test matrix.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from worker.collectors.http import OK, PoliteFetcher
from worker.extractors.feeds import parse_feed
from worker.extractors.jsonld import _blocks, _is_event, _walk
from worker.extractors.news import _plain, candidate_from_item
from worker.extractors.page import extract_all
from worker.extractors.roundup import act_name, extract_roundup
from worker.matching.artists import match_artists_detailed
from worker.stats import Trace
from worker.verification.classify import classify

WIDGETS = ("songkick", "bandsintown", "seated", "ticketmaster", "dice.fm", "eventbrite", "tourlink", "ticketweb",
           "wmgartistservices", "livenation", "axs.com", "eventim", "universe.com", "bookmyshow", "district.in", "insider.in")


def page_profile(html: str) -> Dict[str, Any]:
    """Cheap facts about a static page: how much real text, how many scripts, which widgets/frameworks are present."""
    soup = BeautifulSoup(html, "html.parser")
    scripts = len(soup.find_all("script"))
    for junk in soup(["script", "style", "noscript"]):
        junk.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    low = html.lower()
    framework = next((n for n, k in (("next.js", "__next"), ("nuxt", "__nuxt"), ("react-root", 'id="root"'), ("angular", "ng-app"),
                                    ("gatsby", "___gatsby")) if k in low), None)
    return {"text_chars": len(text), "script_tags": scripts, "widgets": sorted({w for w in WIDGETS if w in low}),
            "framework": framework, "js_heavy": len(text) < 1500 and scripts >= 8, "needs_js_notice": "enable javascript" in low}


def analyze(fetcher: PoliteFetcher, url: str, *, source_type: str = "artist_website", artist: Optional[str] = None,
            catalog: Optional[List[Dict[str, Any]]] = None, now: Optional[dt.datetime] = None, feed: bool = False) -> Dict[str, Any]:
    now = now or dt.datetime.now(dt.timezone.utc)
    res = fetcher.fetch(url)
    out: Dict[str, Any] = {"url": url, "source_type": source_type, "accessible": res.status == OK, "fetch_status": res.status,
                           "detail": res.detail, "final_url": res.url, "events": [], "rejections": {}, "jsonld_events_raw": 0}
    if res.status != OK:
        return out
    trace = Trace(cap=500)
    if feed:
        items = parse_feed(res.text)
        out["feed_items"] = len(items)
        today = now.date()
        for it in items:
            if it.content:
                for ev in extract_roundup(it.content, it.link, today, trace):
                    out["events"].append({"artist": act_name(ev.name), "name": ev.name, "city": ev.city, "venue": ev.venue, "date": ev.event_date,
                                          "booking_url": ev.link, "status": "unconfirmed"})
            for m in match_artists_detailed(_plain(it.title), catalog or []):
                c = candidate_from_item(it, m.artist, now, trace)
                if c:
                    out["events"].append({"artist": m.artist["artist_name"], "name": c.title, "city": c.city, "venue": None, "date": c.event_date,
                                          "booking_url": None, "status": classify("publisher_rss", owner_source=False, ambiguous_name=c.ambiguous_name)})
    else:
        out["profile"] = page_profile(res.text)
        out["jsonld_events_raw"] = sum(1 for b in _blocks(res.text) for n in _walk(b) if isinstance(n, dict) and _is_event(n) and n.get("startDate"))
        for c in extract_all(res.text, res.url, official_owner=source_type == "artist_website", trace=trace):
            if c.event_date < (now - dt.timedelta(days=1)).date().isoformat():
                trace.reject("past_date", c.snippet)
                continue
            if source_type == "artist_website":
                owners = [artist or "(source artist)"]
                conf_ambiguous = False
            else:
                ms = match_artists_detailed(c.snippet, catalog or [])
                owners = [m.artist["artist_name"] for m in ms] or ([act_name(c.event_name)] if c.event_name else [])
                conf_ambiguous = any(m.ambiguous for m in ms)
                if not owners:
                    trace.reject("no_artist_match", c.snippet, stage="matching")
            for o in owners:
                out["events"].append({"artist": o, "name": c.event_name, "city": c.city, "venue": c.venue, "date": c.event_date,
                                      "booking_url": c.booking_url, "status": classify(source_type, owner_source=source_type == "artist_website",
                                                                                      ambiguous_name=conf_ambiguous)})
    out["rejections"] = dict(Counter(r.reason for r in trace.rejections))
    out["rejection_samples"] = [{"reason": r.reason, "snippet": r.snippet[:140], "city": r.city_hint, "date": r.date_hint}
                                for r in trace.rejections[:6]]
    return out

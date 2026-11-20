"""Show candidates from news headlines (Google News RSS). Everything produced here is a SECONDARY report:
it is labelled Unconfirmed on the site, never confirmed, and never triggers alerts.

Strict on purpose, because headlines are noisy: the artist must be named in the headline (ambiguous names are
capped at rumoured by the pipeline), the headline/summary must talk about a live show, it must name exactly one
recognised Indian city and exactly one date, and the article must be recent.
"""
from __future__ import annotations

import datetime as dt
import html as html_lib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from worker.extractors.cities import find_cities
from worker.extractors.dates import find_dates_relative
from worker.extractors.feeds import FeedItem
from worker.matching.artists import match_artists_detailed
from worker.stats import Trace

MAX_AGE_DAYS = 60
_SHOW = re.compile(r"\b(concert|tour|live in|gig|show|perform\w*|headlin\w*|festival|set to|to play|tickets?|presale|pre-sale|dates)\b", re.IGNORECASE)
_NOT_A_SHOW = re.compile(r"\b(review|reviews|interview|recap|photos?|gallery|sold out|cancel\w*|postpone\w*|lawsuit|dies|death|obituary)\b", re.IGNORECASE)


@dataclass
class NewsCandidate:
    city: str
    event_date: str
    title: str
    link: str
    published: dt.datetime
    ambiguous_name: bool


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(html_lib.unescape(text or ""), "html.parser").get_text(" ")).strip()


def candidate_from_item(item: FeedItem, artist: Dict[str, str], now: dt.datetime, trace: Optional[Trace] = None) -> Optional[NewsCandidate]:
    if item.published is None or (now - item.published).days > MAX_AGE_DAYS or item.published > now + dt.timedelta(days=1):
        return None
    title = _plain(item.title)
    summary = _plain(item.summary)
    matches = match_artists_detailed(title, [artist])
    if not matches:
        return None                                   # the artist must be in the headline itself
    text = title + " " + summary
    if not _SHOW.search(title) or _NOT_A_SHOW.search(title):
        return None
    cities = find_cities(text)
    dates = find_dates_relative(text, item.published.date())
    if len(cities) != 1 or len(dates) != 1:
        if trace is not None:                         # the artist IS in the headline and it is about a show: keep the partial candidate
            reason = ("news_multiple_cities" if len(cities) > 1 else "news_no_city" if not cities else
                      "news_multiple_dates" if len(dates) > 1 else "news_no_date")
            trace.reject(reason, title, artist_hint=artist["artist_name"], event_name=title[:200],
                         city_hint=", ".join(cities) or None, date_hint=", ".join(d.isoformat() for d in dates) or None)
        return None                                   # ambiguous or incomplete: skip rather than guess
    if dates[0] < now.date() - dt.timedelta(days=1):
        return None
    return NewsCandidate(cities[0], dates[0].isoformat(), title[:200], item.link, item.published, matches[0].ambiguous)

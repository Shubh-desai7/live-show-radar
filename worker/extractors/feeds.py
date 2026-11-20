"""Generic RSS/Atom parsing (any permitted publisher feed). Not used for Google News unless explicitly enabled."""
from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass
from typing import List, Optional

import feedparser


@dataclass
class FeedItem:
    title: str
    link: str
    summary: str
    published: Optional[dt.datetime]    # timezone-aware UTC


def parse_feed(text: str) -> List[FeedItem]:
    parsed = feedparser.parse(text)
    items: List[FeedItem] = []
    for e in parsed.entries:
        t = e.get("published_parsed") or e.get("updated_parsed")
        published = dt.datetime.fromtimestamp(calendar.timegm(t), tz=dt.timezone.utc) if t else None
        link = e.get("link") or ""
        if link.startswith(("http://", "https://")):
            items.append(FeedItem(e.get("title", ""), link, e.get("summary", ""), published))
    return items

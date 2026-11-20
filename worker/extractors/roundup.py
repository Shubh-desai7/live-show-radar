"""Festival / gig ROUNDUP articles (e.g. Rolling Stone India's "festivals in India" guide).

Format handled: a heading with the event's name, then a date line ("Oct. 3 and 4, 2026"), then a "venue, city" line, then
free text that usually names the lineup. Strict like everything else: explicit year required, exactly one city, a date
that is not in the past. Results are editorial reports: always Unconfirmed.
Any Indian city is accepted (not only the 16 we alert on); an unknown city name is taken from the end of the venue line.
"""
from __future__ import annotations

import datetime as dt
import html as html_lib
import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from worker.extractors.cities import find_cities
from worker.extractors.dates import find_dates

INDIAN_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat", "haryana", "himachal pradesh",
    "jharkhand", "karnataka", "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland", "odisha",
    "punjab", "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "delhi", "jammu and kashmir", "ladakh", "puducherry", "chandigarh", "india",
}
_YEAR_TAIL = re.compile(r"\s*[\(\-–—:]?\s*\b(19|20)\d{2}\b\s*\)?\s*$")


@dataclass
class RoundupEvent:
    name: str
    city: str
    event_date: str
    venue: Optional[str]
    link: Optional[str]            # an external page about the event, if the article links one
    blurb: str                     # the paragraph(s) after the venue line: usually the lineup


def act_name(name: str) -> str:
    """Stable name for an event/festival 'act': no trailing year, single spaces."""
    n = re.sub(r"\s+", " ", html_lib.unescape(name)).strip()
    n = _YEAR_TAIL.sub("", n).strip(" -–—:")
    return n[:120]


def city_from_line(line: str) -> Optional[str]:
    known = find_cities(line)
    if len(known) == 1:
        return known[0]
    if len(known) > 1:
        return None                                 # several cities in one line: ambiguous
    parts = [p.strip() for p in line.split(",") if p.strip()]
    while parts and parts[-1].lower() in INDIAN_STATES:
        parts.pop()
    if not parts:
        return None
    city = parts[-1]
    return city.title() if 2 <= len(city) <= 40 and re.search(r"[A-Za-z]", city) and city.lower() != "tba" else None


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(t)).strip()


def extract_roundup(html: str, base_url: str, today: dt.date) -> List[RoundupEvent]:
    soup = BeautifulSoup(html, "html.parser")
    publisher_host = urlparse(base_url).hostname or ""
    out: List[RoundupEvent] = []
    seen = set()
    for h in soup.find_all(["h2", "h3"]):
        name = _clean(h.get_text(" "))
        paras: List[Tag] = []
        n = h
        while len(paras) < 4:
            n = n.find_next_sibling()
            if n is None or n.name in ("h2", "h3"):
                break
            if n.name == "p":
                paras.append(n)
        if len(paras) < 2 or not name:
            continue
        dates = find_dates(_clean(paras[0].get_text(" ")))
        if not dates:
            continue
        date = dates[0]
        venue_line = _clean(paras[1].get_text(" "))
        city = city_from_line(venue_line)
        if not city or date < today - dt.timedelta(days=1):
            continue
        link = None
        for p in paras[1:]:
            for a in p.find_all("a", href=True):
                url = urljoin(base_url, a["href"])
                if urlparse(url).scheme in ("http", "https") and (urlparse(url).hostname or "") != publisher_host:
                    link = url[:500]
                    break
            if link:
                break
        venue = None if venue_line.lower().startswith("tba") or "multiple" in venue_line.lower() else venue_line[:200]
        key = (name.lower(), date.isoformat(), city)
        if key in seen:
            continue
        seen.add(key)
        out.append(RoundupEvent(name, city, date.isoformat(), venue, link, " ".join(_clean(p.get_text(" ")) for p in paras[2:])))
    return out

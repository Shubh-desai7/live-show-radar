"""Extract concert candidates from an official artist / promoter web page.

A candidate needs a recognised Indian city AND an explicit full date in the same page block.
Venue is left unset: guessing it from free text would risk inventing information.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from worker.extractors.cities import find_cities
from worker.extractors.dates import find_dates, find_yearless_dates, has_ambiguous_numeric_date
from worker.extractors.tickets import TicketInfo, blank_ticket_dates
from worker.stats import Trace

_BLOCK_TAGS = ("article", "li", "tr", "section")
_EVENT_CLASS = re.compile(r"event|show|tour|gig|concert|date", re.IGNORECASE)
_TICKET_LINK = re.compile(r"ticket|book|buy|register|rsvp|bookmyshow|insider\.in|district\.in|paytm|ticketmaster", re.IGNORECASE)
MIN_LEN, MAX_LEN = 12, 500
_SHOWWORD = re.compile(r"\b(tour|live|concert|gig|shows?|festival|tickets?|presale|pre-sale|on sale|line-?up|performs?|headlin\w*)\b", re.IGNORECASE)


_CANCELLED = re.compile(r"\b(cancell?ed|called off)\b", re.IGNORECASE)
_POSTPONED = re.compile(r"\b(postponed|rescheduled)\b", re.IGNORECASE)


def detect_status(text: str) -> str:
    """scheduled | cancelled | postponed, from explicit wording in the block only."""
    if _CANCELLED.search(text):
        return "cancelled"
    if _POSTPONED.search(text):
        return "postponed"
    return "scheduled"


@dataclass
class Candidate:
    city: str
    event_date: str                 # YYYY-MM-DD
    snippet: str
    booking_url: Optional[str] = None
    status: str = "scheduled"
    text: str = ""                  # full block text (<= MAX_LEN), used for ticket extraction
    venue: Optional[str] = None     # only from structured data (never guessed from free text)
    event_name: Optional[str] = None
    performers: List[str] = field(default_factory=list)
    tickets: Optional[TicketInfo] = None   # precomputed from structured offers, if any


def _block_text(el: Tag) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True))


def _booking_url(el: Tag, base_url: str) -> Optional[str]:
    for a in el.find_all("a", href=True):
        if _TICKET_LINK.search(a.get_text(" ", strip=True)) or _TICKET_LINK.search(a["href"]):
            url = urljoin(base_url, a["href"])
            if urlparse(url).scheme in ("http", "https"):
                return url
    return None


def _blocks(soup: BeautifulSoup) -> List[Tag]:
    blocks = list(soup.find_all(_BLOCK_TAGS))
    blocks += [d for d in soup.find_all("div") if _EVENT_CLASS.search(" ".join(d.get("class", [])))]
    return blocks


def extract_candidates(html: str, base_url: str, trace: Optional[Trace] = None) -> List[Candidate]:
    soup = BeautifulSoup(html, "html.parser")
    for junk in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        junk.decompose()

    out: List[Candidate] = []
    seen = set()
    # Smallest blocks first so a list item wins over the whole list that contains it.
    for el in sorted(_blocks(soup), key=lambda e: len(_block_text(e))):
        text = _block_text(el)
        if not (MIN_LEN <= len(text) <= MAX_LEN):
            continue
        show_text = blank_ticket_dates(text)           # sale/registration dates are not the show date
        cities, dates = find_cities(show_text), find_dates(show_text)
        if len(cities) != 1 or len(dates) != 1:      # ambiguous block: skip rather than guess
            if trace is not None:
                _explain(trace, el, text, show_text, cities, dates)
            continue
        key = (cities[0], dates[0].isoformat())
        if key in seen:
            continue
        seen.add(key)
        out.append(Candidate(cities[0], dates[0].isoformat(), text[:300], _booking_url(el, base_url), detect_status(text), text))
    return out


def _explain(trace: Trace, el: Tag, text: str, show_text: str, cities: List[str], dates) -> None:
    """Record WHY a block that carried event signals was not turned into an event (nothing is created from it)."""
    signal = bool(_SHOWWORD.search(text)) or bool(_EVENT_CLASS.search(" ".join(el.get("class", []))))
    yearless = find_yearless_dates(show_text)
    hint = ", ".join(d.isoformat() for d in dates[:3]) or (", ".join(yearless[:3]) or None)
    city = ", ".join(cities[:3]) or None
    if len(cities) > 1 and dates:
        trace.reject("multiple_cities", text, city_hint=city, date_hint=hint)
    elif len(dates) > 1 and len(cities) == 1:
        trace.reject("multiple_dates", text, city_hint=city, date_hint=hint)
    elif len(cities) == 1 and not dates:
        if has_ambiguous_numeric_date(show_text):
            trace.reject("ambiguous_numeric_date", text, city_hint=city)
        elif yearless and signal:
            trace.reject("date_without_year", text, city_hint=city, date_hint=hint)
        elif signal:
            trace.reject("no_date", text, city_hint=city)
    elif len(dates) == 1 and not cities and signal:
        trace.reject("no_city", text, date_hint=hint)

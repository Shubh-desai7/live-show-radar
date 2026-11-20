"""schema.org Event extraction from JSON-LD blocks (<script type="application/ld+json">) in static HTML.

Structured data is far more reliable than guessing from text, so venue, name and sale start can be used directly.
Still treated as untrusted input: strings are sanitised and length-capped, URLs must be http(s), only events with a
recognised Indian city and a valid date are kept, online-only events are skipped.
"""
from __future__ import annotations

import datetime as dt
import html as html_lib
import json
import re
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from worker.extractors.cities import find_cities
from worker.extractors.html_events import Candidate
from worker.extractors.tickets import GENERAL_SALE, IST, PRESALE_OPENING, Moment, TicketInfo

MAX_EVENTS = 200
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
_PRESALE_WORDS = re.compile(r"pre[-\s]?sale|early\s*access|members?\s*only|fan\s*club", re.IGNORECASE)
_EARLY_BIRD = re.compile(r"early[-\s]?bird", re.IGNORECASE)


def _clean(value: Any, limit: int = 200) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = html_lib.unescape(value)                   # sites often leave &#8211; / &amp; entities in JSON strings
    text = _CTRL.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] or None


def _types(node: Dict[str, Any]) -> List[str]:
    t = node.get("@type")
    return [x for x in (t if isinstance(t, list) else [t]) if isinstance(x, str)]


def _is_event(node: Dict[str, Any]) -> bool:
    return any(t.endswith("Event") or t == "Festival" for t in _types(node))


def _walk(node: Any, depth: int = 0) -> Iterator[Dict[str, Any]]:
    """Yield every dict in a JSON-LD tree (handles @graph, arrays, ItemList, nested subEvent/event)."""
    if depth > 8:
        return
    if isinstance(node, list):
        for x in node:
            yield from _walk(x, depth + 1)
    elif isinstance(node, dict):
        yield node
        for v in node.values():
            if isinstance(v, (dict, list)):
                yield from _walk(v, depth + 1)


def _blocks(html: str) -> Iterator[Any]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = (tag.string or tag.get_text() or "").strip()
        raw = re.sub(r"^\s*(?:<!--|//<!\[CDATA\[)|(?:-->|//\]\]>)\s*$", "", raw).strip()
        try:
            yield json.loads(raw)
        except (ValueError, RecursionError):
            continue


# Event plugins often emit these as the performer "name"; they identify nobody and must not feed artist matching.
_GENERIC_PERFORMERS = {"organization", "person", "performer", "musicgroup", "artist", "tba", "tbc", "various artists", "n/a", "na"}


def _name_of(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        return _clean(value.get("name"))
    return _clean(value)


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else ([] if value is None else [value])


def _location(ev: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """venue name and the text to search for a city; online-only locations yield no city."""
    venue, haystack = None, []
    for loc in _as_list(ev.get("location")):
        if isinstance(loc, dict):
            if "VirtualLocation" in _types(loc):
                continue
            venue = venue or _clean(loc.get("name"))
            addr = loc.get("address")
            if isinstance(addr, dict):
                haystack += [str(addr.get(k, "")) for k in ("addressLocality", "addressRegion", "streetAddress")]
            elif isinstance(addr, str):
                haystack.append(addr)
            haystack.append(loc.get("name", "") if isinstance(loc.get("name"), str) else "")
        elif isinstance(loc, str):
            haystack.append(loc)
    return {"venue": venue, "haystack": " ".join(haystack)}


def _start_date(value: Any) -> Optional[str]:
    """Local calendar date of the event. JSON-LD gives it in the venue's own offset, so the leading date is right."""
    if not isinstance(value, str):
        return None
    m = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})", value)
    if not m:
        return None
    try:
        return dt.date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    except ValueError:
        return None


def _moment(value: Any) -> Optional[Moment]:
    """Offer.validFrom -> Moment. Precise only with an explicit time AND zone; otherwise stored as 00:00 IST, imprecise."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    try:
        if re.search(r"T\d{2}:\d{2}", v):
            d = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
            precise = d.tzinfo is not None
            return Moment((d if d.tzinfo else d.replace(tzinfo=IST)).astimezone(dt.timezone.utc), precise)
        day = dt.date.fromisoformat(v[:10])
        return Moment(dt.datetime(day.year, day.month, day.day, tzinfo=IST).astimezone(dt.timezone.utc), False)
    except ValueError:
        return None


def _offers(ev: Dict[str, Any], base_url: str):
    info, url = TicketInfo(), None
    for offer in _as_list(ev.get("offers")):
        if not isinstance(offer, dict):
            continue
        link = offer.get("url")
        if url is None and isinstance(link, str):
            absolute = urljoin(base_url, link.strip())
            if urlparse(absolute).scheme in ("http", "https"):
                url = absolute[:500]
        label = " ".join(x for x in (_clean(offer.get("name")), _clean(offer.get("description"))) if x)
        if _EARLY_BIRD.search(label):
            if info.early_bird_status == "unknown":
                info.early_bird_status = "available"
            continue                                   # an early-bird tier says nothing about when sales open
        m = _moment(offer.get("validFrom"))
        if m is None:
            continue
        key = PRESALE_OPENING if _PRESALE_WORDS.search(label) else GENERAL_SALE
        info.moments.setdefault(key, m)
    return info, url


def extract_jsonld_events(html: str, base_url: str) -> List[Candidate]:
    out: List[Candidate] = []
    seen = set()
    for block in _blocks(html):
        for node in _walk(block):
            if not _is_event(node) or len(out) >= MAX_EVENTS:
                continue
            attendance = str(node.get("eventAttendanceMode", ""))
            if attendance.endswith("OnlineEventAttendanceMode"):
                continue
            date = _start_date(node.get("startDate"))
            loc = _location(node)
            cities = find_cities(loc["haystack"] or "")
            if not date or len(cities) != 1:
                continue                                # unknown/ambiguous city or date: skip rather than guess
            key = (cities[0], date, (_name_of(node.get("name")) or "").lower())
            if key in seen:
                continue
            seen.add(key)
            status = str(node.get("eventStatus", ""))
            tickets, offer_url = _offers(node, base_url)
            link = node.get("url")
            if offer_url is None and isinstance(link, str):
                absolute = urljoin(base_url, link.strip())
                offer_url = absolute[:500] if urlparse(absolute).scheme in ("http", "https") else None
            performers = [n for n in (_name_of(p) for p in _as_list(node.get("performer")) + _as_list(node.get("headliner")))
                          if n and n.lower() not in _GENERIC_PERFORMERS]
            name = _clean(node.get("name"))
            out.append(Candidate(
                city=cities[0], event_date=date,
                snippet=" ".join([name or ""] + performers)[:300],
                booking_url=offer_url,
                status="cancelled" if status.endswith("EventCancelled") else
                       "postponed" if status.endswith(("EventPostponed", "EventRescheduled")) else "scheduled",
                text=" ".join([name or "", loc["venue"] or ""] + performers)[:500],
                venue=loc["venue"], event_name=name, performers=performers,
                tickets=tickets if (tickets.moments or tickets.early_bird_status != "unknown") else None))
    return out

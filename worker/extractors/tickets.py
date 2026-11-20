"""Ticket-sale intelligence from the text of one event block.

Extracts: presale registration deadline, presale opening, general sale opening, early-bird status.
Rules (never invent):
  * a moment needs an explicit date WITH a year; a missing year means the moment is ignored;
  * a moment with a time of day is "precise"; a date-only moment is stored as 00:00 IST and is NOT precise;
  * a bare time (no zone) is read as IST (all supported cities are in India); IST/UTC/GMT/explicit offsets are understood;
    any other zone abbreviation (EST, PST...) makes the moment imprecise;
  * moments on/after the event date are discarded (they would be misreads);
  * `reliable` is True only if every extracted moment is precise. The pipeline additionally requires an official source.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from worker.extractors.dates import find_date_spans, find_dates

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
WINDOW = 120

PRESALE_REGISTRATION = "presale_registration_deadline"
PRESALE_OPENING = "presale_opening"
GENERAL_SALE = "general_sale_opening"

_TIME12 = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.IGNORECASE)
_TIME24 = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b(?!\s*(?:am|pm))", re.IGNORECASE)
_TZ = re.compile(r"\b(IST|UTC|GMT|EST|EDT|CST|CDT|MST|MDT|PST|PDT|BST|CET|CEST|EET|SGT|JST|AEST|AEDT|GST|HKT|PKT|NPT)\b(?:\s*([+-])\s*(\d{1,2})(?::?([0-5]\d))?)?|([+-])(\d{2}):?([0-5]\d)\b")
_KNOWN_ZONES = {"IST", "UTC", "GMT"}

_REG_CUE = re.compile(r"\b(by|before|until|till|closes?|closing|ends?|deadline)\b", re.IGNORECASE)
_GENERAL = re.compile(r"\b(?:(?:general|public)\s+(?:ticket\s+)?(?:on[-\s]?)?sale|tickets?\s+(?:go(?:es)?\s+)?on[-\s]?sale|on[-\s]sale)\b", re.IGNORECASE)
_PRESALE = re.compile(r"\bpre[-\s]?sale\b", re.IGNORECASE)
_REGIST = re.compile(r"\bregist\w*\b", re.IGNORECASE)
_EARLY = re.compile(r"\bearly[-\s]?bird\b", re.IGNORECASE)


@dataclass
class Moment:
    at: dt.datetime            # UTC
    precise: bool


@dataclass
class TicketInfo:
    moments: Dict[str, Moment] = field(default_factory=dict)
    early_bird_status: str = "unknown"

    @property
    def reliable(self) -> bool:
        return bool(self.moments) and all(m.precise for m in self.moments.values())

    def is_empty(self) -> bool:
        return not self.moments and self.early_bird_status == "unknown"


def _parse_moment(window: str) -> Optional[Moment]:
    dates = find_dates(window)
    if not dates:
        return None
    day = dates[0]
    t12, t24 = _TIME12.search(window), _TIME24.search(window)
    if t12:
        hour, minute = int(t12.group(1)) % 12, int(t12.group(2) or 0)
        if not 1 <= int(t12.group(1)) <= 12:
            t12 = None
        else:
            hour += 12 if t12.group(3).lower() == "pm" else 0
    if not t12 and t24:
        hour, minute = int(t24.group(1)), int(t24.group(2))
    if not (t12 or t24):
        return Moment(dt.datetime(day.year, day.month, day.day, tzinfo=IST).astimezone(dt.timezone.utc), False)

    tz, precise = IST, True
    m = _TZ.search(window)
    if m:
        if m.group(5):                                      # +05:30
            sign = 1 if m.group(5) == "+" else -1
            tz = dt.timezone(sign * dt.timedelta(hours=int(m.group(6)), minutes=int(m.group(7))))
        elif m.group(1) in _KNOWN_ZONES:
            if m.group(2):                                  # GMT+5:30 / UTC+5
                sign = 1 if m.group(2) == "+" else -1
                tz = dt.timezone(sign * dt.timedelta(hours=int(m.group(3)), minutes=int(m.group(4) or 0)))
            elif m.group(1) == "IST":
                tz = IST
            else:
                tz = dt.timezone.utc
        else:
            precise = False                                 # EST, PST...: unknown zone
    local = dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
    return Moment(local.astimezone(dt.timezone.utc), precise)


def _anchors(text: str) -> List[Tuple[int, int, Optional[str]]]:
    """(start, end, kind) where kind None marks a boundary that claims no date."""
    found: List[Tuple[int, int, Optional[str]]] = []
    for m in _REGIST.finditer(text):
        cue = _REG_CUE.search(text, m.end(), m.end() + 45)
        found.append((m.start(), cue.end() if cue else m.end(), PRESALE_REGISTRATION if cue else None))
    for m in _PRESALE.finditer(text):
        near = text[m.end(): m.end() + 30]
        found.append((m.start(), m.end(), None if _REGIST.search(near) else PRESALE_OPENING))
    for m in _GENERAL.finditer(text):
        found.append((m.start(), m.end(), GENERAL_SALE))
    for m in _EARLY.finditer(text):
        found.append((m.start(), m.end(), None))
    found.sort()
    kept: List[Tuple[int, int, Optional[str]]] = []
    for a in found:                                         # drop anchors swallowed by the previous one
        if kept and a[0] < kept[-1][1]:
            continue
        kept.append(a)
    return kept


def _early_bird(text: str) -> str:
    for m in _EARLY.finditer(text):
        ctx = text[max(0, m.start() - 40): m.end() + 60]
        if re.search(r"\bno\s+early", ctx, re.IGNORECASE):
            return "not_offered"
        if re.search(r"sold\s*out|\bended\b|\bclosed\b|\bover\b|expired|no longer", ctx, re.IGNORECASE):
            return "ended"
        if re.search(r"\bavailable\b|\bnow\b|\blive\b|on\s+sale|\btill\b|\buntil\b|\bvalid\b|\blimited\b|\bgrab\b", ctx, re.IGNORECASE):
            return "available"
    return "unknown"


def extract_ticket_info(text: str, event_date: Optional[str] = None) -> TicketInfo:
    info = TicketInfo(early_bird_status=_early_bird(text))
    anchors = _anchors(text)
    for i, (_, end, kind) in enumerate(anchors):
        if kind is None or kind in info.moments:
            continue
        stop = anchors[i + 1][0] if i + 1 < len(anchors) else len(text)
        moment = _parse_moment(text[end: min(end + WINDOW, stop)])
        if moment is None:
            continue
        if event_date and moment.at.astimezone(IST).date().isoformat() >= event_date:
            continue                                        # a sale on/after show day is a misread
        info.moments[kind] = moment
    return info


def blank_ticket_dates(text: str) -> str:
    """Replace the dates that belong to ticket-sale wording with spaces, so what is left can be searched for the show date."""
    chars = list(text)
    anchors = _anchors(text)
    for i, (_, end, kind) in enumerate(anchors):
        if kind is None:
            continue
        stop = anchors[i + 1][0] if i + 1 < len(anchors) else len(text)
        window_end = min(end + WINDOW, stop)
        spans = find_date_spans(text[end:window_end])
        if spans:
            s0, e0, _ = spans[0]
            for j in range(end + s0, end + e0):
                chars[j] = " "
    return "".join(chars)

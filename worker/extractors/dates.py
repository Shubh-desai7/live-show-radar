"""Date extraction. Only dates with an explicit year are returned: we never guess a missing year."""
from __future__ import annotations

import datetime as dt
import re
from typing import List, Tuple

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
_M = r"(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")"
_SUFFIX = r"(?:st|nd|rd|th)?"
_RANGE = r"(?:\s*[-–]\s*\d{1,2}" + _SUFFIX + r")?"   # "20-21": the start day is captured

# 20 Dec 2026 / 20th December, 2026 / 20-21 Dec 2026
_DMY = re.compile(r"\b(\d{1,2})" + _SUFFIX + _RANGE + r"\s+" + _M + r"\.?,?\s+(\d{4})\b", re.IGNORECASE)
# Dec 20, 2026 / December 20th 2026
_MDY = re.compile(r"\b" + _M + r"\.?\s+(\d{1,2})" + _SUFFIX + _RANGE + r",?\s+(\d{4})\b", re.IGNORECASE)
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _make(y: int, m: int, d: int):
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def find_date_spans(text: str) -> List[Tuple[int, int, dt.date]]:
    """(start, end, date) for every valid date with an explicit year, in order of appearance."""
    found = []
    for m in _DMY.finditer(text):
        found.append((m.start(), m.end(), _make(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))))
    for m in _MDY.finditer(text):
        found.append((m.start(), m.end(), _make(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))))
    for m in _ISO.finditer(text):
        found.append((m.start(), m.end(), _make(int(m.group(1)), int(m.group(2)), int(m.group(3)))))
    return [f for f in sorted(found, key=lambda x: x[0]) if f[2] is not None]


def find_dates(text: str) -> List[dt.date]:
    """Dates with an explicit year, in order of appearance, without duplicates."""
    out: List[dt.date] = []
    for _, _, d in find_date_spans(text):
        if d not in out:
            out.append(d)
    return out


# ---------------------------------------------------------------- news: day + month without a year
_DM = re.compile(r"\b(\d{1,2})" + _SUFFIX + _RANGE + r"\s+" + _M + r"\b(?!\.?,?\s+\d{4})", re.IGNORECASE)
_MD = re.compile(r"\b" + _M + r"\.?\s+(\d{1,2})" + _SUFFIX + _RANGE + r"\b(?!,?\s+\d{4})", re.IGNORECASE)


def find_dates_relative(text: str, published: dt.date) -> List[dt.date]:
    """News headlines say "Nov 27" without a year. Dates with an explicit year are used as written; a bare day+month is
    read as its next occurrence on or after (published date - 1 day), never more than ~12 months ahead. Only for sources
    that are labelled Unconfirmed: a published date is a strong anchor, but it is still an inference."""
    explicit = find_dates(text)
    if explicit:
        return explicit
    found = []
    for m in _DM.finditer(text):
        found.append((m.start(), int(m.group(1)), _MONTHS[m.group(2).lower()]))
    for m in _MD.finditer(text):
        found.append((m.start(), int(m.group(2)), _MONTHS[m.group(1).lower()]))
    out: List[dt.date] = []
    floor, ceiling = published - dt.timedelta(days=1), published + dt.timedelta(days=300)
    for _, day, month in sorted(found):
        for year in (published.year, published.year + 1):
            d = _make(year, month, day)
            if d is not None and d >= floor:
                if d <= ceiling and d not in out:      # a "date" almost a year out is far more likely a past date
                    out.append(d)
                break
    return out

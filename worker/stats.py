"""Run statistics and rejection tracking.

Extractors accept an optional `Trace`: whenever a block/record that carried SOME event signal (a date, a city, a show
word) is not turned into an event, they call `trace.reject(...)` with a machine-readable reason. Nothing here changes what
is stored as an event: it only makes the loss visible and keeps the partial candidate for review.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Reason codes (stage in brackets). Keep stable: they are stored and shown on the diagnostics page.
REASONS = {
    "no_city": "date found but no recognised Indian city [extraction]",
    "no_date": "city found but no date [extraction]",
    "date_without_year": "day and month found but no year [extraction]",
    "ambiguous_numeric_date": "numeric date such as 05/06/2026 could be day/month or month/day [extraction]",
    "multiple_cities": "more than one city in the same block [extraction]",
    "multiple_dates": "more than one date in the same block [extraction]",
    "city_not_recognised": "structured event whose location is not a recognised Indian city [extraction]",
    "online_event": "online-only event [extraction]",
    "past_date": "event date already passed [extraction]",
    "no_artist_match": "event found but no catalog artist named in it [matching]",
    "status_notice_untracked": "cancellation/postponement notice for a show we never tracked [verification]",
    "news_no_city": "headline names a catalog artist and a show but no city [extraction]",
    "news_no_date": "headline names a catalog artist and a show but no date [extraction]",
    "news_multiple_cities": "headline names several cities [extraction]",
    "news_multiple_dates": "headline names several dates [extraction]",
    "roundup_no_date": "roundup entry without a usable date [extraction]",
    "roundup_no_city": "roundup entry without a usable city [extraction]",
}
CITY_DATE_FAILURES = {"no_city", "no_date", "date_without_year", "ambiguous_numeric_date", "multiple_cities", "multiple_dates",
                      "city_not_recognised", "news_no_city", "news_no_date", "news_multiple_cities", "news_multiple_dates",
                      "roundup_no_date", "roundup_no_city"}
MAX_PER_SOURCE = 60


@dataclass
class Rejection:
    stage: str
    reason: str
    detail: str = ""
    artist_hint: Optional[str] = None
    event_name: Optional[str] = None
    city_hint: Optional[str] = None
    date_hint: Optional[str] = None
    venue: Optional[str] = None
    booking_url: Optional[str] = None
    snippet: str = ""

    def key(self) -> str:
        return hashlib.sha1(("%s|%s|%s" % (self.reason, self.event_name or "", self.snippet[:160])).encode("utf-8")).hexdigest()


class Trace:
    """Collects rejections for one source. Safe to pass as None everywhere (callers check)."""
    def __init__(self, cap: int = MAX_PER_SOURCE) -> None:
        self.rejections: List[Rejection] = []
        self.cap = cap

    def reject(self, reason: str, snippet: str = "", stage: str = "extraction", **fields: Any) -> None:
        if len(self.rejections) < self.cap:
            snippet = re.sub(r"\s+", " ", snippet).strip()[:300]
            self.rejections.append(Rejection(stage=stage, reason=reason, snippet=snippet, **fields))

    def counts(self) -> Counter:
        return Counter(r.reason for r in self.rejections)


@dataclass
class SourceResult:
    source_id: Optional[str]
    source_url: str
    status: str
    detail: str = ""
    candidates: int = 0
    rejected: int = 0
    events_new: int = 0
    duration_ms: int = 0


@dataclass
class RunReport:
    """Everything recorded about one run; flushed to the database by worker.main."""
    command: str = "discover"
    trigger: str = "manual"
    counters: Counter = field(default_factory=Counter)
    reasons: Counter = field(default_factory=Counter)
    source_results: List[SourceResult] = field(default_factory=list)
    candidates: List[tuple] = field(default_factory=list)       # (source_id, Rejection)

    def add_rejections(self, source_id: Optional[str], trace: Optional[Trace]) -> int:
        if trace is None:
            return 0
        for r in trace.rejections:
            self.reasons[r.reason] += 1
            self.candidates.append((source_id, r))
        return len(trace.rejections)

    def summary(self) -> Dict[str, Any]:
        c = dict(self.counters)
        c["candidates_rejected"] = sum(self.reasons.values())
        c["city_date_failures"] = sum(n for r, n in self.reasons.items() if r in CITY_DATE_FAILURES)
        c["rejection_reasons"] = dict(self.reasons)
        return c

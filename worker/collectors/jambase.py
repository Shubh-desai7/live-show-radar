"""JamBase Data API collector (licensed event database; https://data.jambase.com).

Terms (read 2026-11-21): the free *Developer* plan allows hobby / non-commercial apps, a synced local copy while the account
is active, and requires attribution ("Concert data by JamBase"); ticket links must be shown as returned. The 14-day *trial*
forbids production use and derivative databases and requires deleting stored data, so writing is refused unless
JAMBASE_PLAN=developer is set. Calls are budgeted: one sync pulls India's upcoming events in 1-3 calls and runs at most
every 6 hours (~120 calls/month against a 1,000 quota).
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

from worker import config

log = logging.getLogger("worker")
BASE = "https://api.data.jambase.com/v3"
SOURCE_URL = BASE + "/events?geoCountryIso2=IN"        # the `sources` row for this channel
RECHECK_HOURS = 6
MAX_PAGES = 3
PER_PAGE = 100
MAX_EVENTS = 300


@dataclass
class JamEvent:
    source_event_id: str
    name: str
    performers: List[str]
    date: str                               # YYYY-MM-DD (local date as published)
    city_text: str                          # locality / region text used for city recognition
    venue: Optional[str]
    ticket_url: Optional[str]
    status: str                             # scheduled | cancelled | postponed
    url: Optional[str]
    modified: Optional[str]
    raw_city: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


def _name(v: Any) -> str:
    if isinstance(v, dict):
        v = v.get("name")
    return str(v).strip() if v else ""


def parse_event(e: Dict[str, Any]) -> Optional[JamEvent]:
    start = str(e.get("startDate") or "")[:10]
    if len(start) != 10 or str(e.get("eventAttendanceMode", "")).endswith("OnlineEventAttendanceMode"):
        return None
    loc = e.get("location") or {}
    addr = loc.get("address") or {}
    locality = _name(addr.get("addressLocality"))
    region = _name(addr.get("addressRegion"))
    status = str(e.get("eventStatus", ""))
    offers = e.get("offers") or []
    ticket = next((o.get("url") for o in offers if isinstance(o, dict) and str(o.get("url", "")).startswith(("http://", "https://"))), None)
    return JamEvent(
        source_event_id=str(e.get("identifier") or ""), name=_name(e.get("name"))[:200],
        performers=[n for n in (_name(p) for p in (e.get("performer") or [])) if n][:60],
        date=start, city_text=" ".join(x for x in (locality, region) if x), raw_city=locality,
        venue=_name(loc.get("name"))[:200] or None, ticket_url=ticket[:500] if ticket else None,
        status="cancelled" if status.endswith("EventCancelled") else "postponed" if status.endswith(("EventPostponed", "EventRescheduled")) else "scheduled",
        url=e.get("url") if str(e.get("url", "")).startswith(("http://", "https://")) else None,
        modified=e.get("dateModified"))


class JamBaseClient:
    def __init__(self, key: Optional[str] = None, session: Optional[requests.Session] = None, sleep=time.sleep) -> None:
        self.key = key if key is not None else os.environ.get("JAMBASE_API_KEY", "")
        self.session = session or requests.Session()
        self._sleep = sleep
        self.calls = 0

    @property
    def configured(self) -> bool:
        return bool(self.key)

    @staticmethod
    def writes_allowed() -> bool:
        return os.environ.get("JAMBASE_PLAN", "") == "developer"

    def fetch_india(self, today: dt.date) -> Dict[str, Any]:
        """{'events': [...], 'status': 'ok'|'unauthorized'|'rate_limited'|'error', 'calls': n}. Never raises."""
        out: List[JamEvent] = []
        for page in range(1, MAX_PAGES + 1):
            self.calls += 1
            try:
                r = self.session.get(BASE + "/events", timeout=config.REQUEST_TIMEOUT, headers={
                    "Authorization": "Bearer " + self.key, "User-Agent": config.USER_AGENT, "Accept": "application/json"},
                    params={"geoCountryIso2": "IN", "eventDateFrom": today.isoformat(), "perPage": PER_PAGE, "page": page})
            except requests.RequestException as exc:
                return {"events": out, "status": "error", "detail": type(exc).__name__, "calls": self.calls}
            if r.status_code in (401, 403):
                return {"events": out, "status": "unauthorized", "detail": "HTTP %d" % r.status_code, "calls": self.calls}
            if r.status_code == 429:
                return {"events": out, "status": "rate_limited", "detail": "HTTP 429", "calls": self.calls}
            if r.status_code != 200:
                return {"events": out, "status": "error", "detail": "HTTP %d" % r.status_code, "calls": self.calls}
            try:
                body = r.json()
            except ValueError:
                return {"events": out, "status": "error", "detail": "bad json", "calls": self.calls}
            raw = body.get("events") or []
            out += [ev for ev in (parse_event(x) for x in raw) if ev]
            if len(raw) < PER_PAGE or len(out) >= MAX_EVENTS:
                break
            self._sleep(7)                                   # trial/dev limit is 10 requests/minute
        return {"events": out[:MAX_EVENTS], "status": "ok", "detail": "", "calls": self.calls}

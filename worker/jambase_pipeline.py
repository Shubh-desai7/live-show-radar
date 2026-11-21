"""JamBase sync: India's upcoming events -> UNCONFIRMED reports through the normal tables.

Rules: never confirmed (secondary source), never alerts, never modifies an existing event (an official source may later
upgrade it), cancelled/postponed events are not created, a city must be recognised from the data JamBase provides
(never guessed), and ticket links are stored exactly as returned.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Dict, List, Optional

from worker.collectors.jambase import RECHECK_HOURS, SOURCE_URL, JamBaseClient, JamEvent
from worker.extractors.cities import find_cities
from worker.extractors.roundup import act_name
from worker.matching.artists import match_artists_detailed
from worker.stats import RunReport, SourceResult, Trace
from worker.verification.classify import classify

log = logging.getLogger("worker")


def _city(ev: JamEvent) -> Optional[str]:
    for text in (ev.city_text, ev.name):
        cities = find_cities(text)
        if len(cities) == 1:
            return cities[0]
    return None


def run_jambase(repo, client: JamBaseClient, catalog: List[Dict[str, Any]], *, now: dt.datetime, dry_run: bool = False,
                report: Optional[RunReport] = None) -> Dict[str, Any]:
    report = report if report is not None else RunReport()
    stats: Dict[str, Any] = {"jambase_status": "skipped", "jambase_events": 0, "jambase_new": 0, "jambase_calls": 0}
    if not client.configured:
        return stats
    if not dry_run and not client.writes_allowed():
        stats["jambase_status"] = "refused_not_developer_plan"       # trial keys are evaluation-only
        return stats
    stamp = now.isoformat()
    due = None
    if not dry_run:
        repo.ensure_source("jambase", SOURCE_URL, None)
        due = repo.jambase_source()
    if due and due.get("last_checked_at"):
        last = dt.datetime.fromisoformat(str(due["last_checked_at"]).replace("Z", "+00:00"))
        if (now - last).total_seconds() < RECHECK_HOURS * 3600:
            stats["jambase_status"] = "not_due"
            return stats
    source_id = (due or {}).get("source_id")
    report.counters["sources_attempted"] += 1
    res = client.fetch_india(now.date())
    stats["jambase_status"], stats["jambase_calls"] = res["status"], res["calls"]
    sres = SourceResult(source_id, SOURCE_URL, res["status"], res.get("detail", ""))
    report.source_results.append(sres)
    trace = Trace()
    if res["status"] != "ok":
        report.counters["sources_blocked" if res["status"] == "unauthorized" else "sources_failed"] += 1
        if not dry_run and source_id:
            repo.update_source(source_id, "blocked" if res["status"] == "unauthorized" else "error", stamp)
        return stats
    report.counters["sources_fetched"] += 1
    report.counters["sources_new_content"] += 1
    for ev in res["events"]:
        stats["jambase_events"] += 1
        if ev.date < (now - dt.timedelta(days=1)).date().isoformat():
            continue
        if ev.status != "scheduled":
            trace.reject("status_notice_untracked", ev.name, stage="verification", event_name=ev.name, date_hint=ev.date)
            continue
        city = _city(ev)
        if not city:
            trace.reject("city_not_recognised", ev.name, event_name=ev.name, city_hint=ev.city_text[:80], date_hint=ev.date, venue=ev.venue)
            continue
        targets = []                                           # (artist_id|None, label, ambiguous)
        for m in match_artists_detailed(" ".join(ev.performers), catalog) if ev.performers else []:
            targets.append((m.artist["artist_id"], m.artist["artist_name"], m.ambiguous))
        if len(ev.performers) > 1 or not ev.performers:
            targets.insert(0, (None, act_name(ev.name), False))
        elif not targets:
            targets.append((None, ev.performers[0], False))
        for artist_id, label, ambiguous in targets:
            report.counters["candidates_extracted"] += 1
            if dry_run:
                stats["jambase_new"] += 1
                continue
            if artist_id is None:
                artist_id = repo.ensure_act_artist(label)
                if artist_id is None:
                    continue
            if repo.find_event(artist_id, city, ev.date):
                report.counters["duplicates_ignored"] += 1
                continue
            confidence = classify("jambase", owner_source=False, ambiguous_name=ambiguous)
            evsrc = repo.jambase_event_source(ev.url or ev.source_event_id, artist_id)
            repo.insert_event({
                "artist_id": artist_id, "city": city, "event_date": ev.date, "venue": ev.venue, "event_name": ev.name,
                "booking_url": ev.ticket_url, "source_id": evsrc or source_id, "confidence": confidence, "status": "scheduled",
                "source_published_at": ev.modified, "first_seen_at": stamp, "detected_at": stamp})
            report.counters["events_created_" + confidence] += 1
            stats["jambase_new"] += 1
            sres.events_new += 1
            log.info("jambase (%s): %s | %s | %s", confidence, label, city, ev.date)
    sres.rejected = report.add_rejections(source_id, trace) if source_id else 0
    if not dry_run and source_id:
        repo.update_source(source_id, "ok", stamp)
    return stats

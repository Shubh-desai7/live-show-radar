"""Discovery pipeline: read sources, collect, extract, match, classify, verify, save.

Workflow steps covered: 1-11 (notification triggering is the optional `on_change` hook, wired in step 10).
Classification rules live in worker/verification/classify.py.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from worker import config
from worker.collectors.http import OK, PoliteFetcher
from worker.extractors.page import extract_all
from worker.extractors.roundup import act_name
from worker.extractors.tickets import drop_late_moments, extract_ticket_info
from worker.matching.artists import Match, match_artists_detailed
from worker.verification.classify import CONFIRMED, RANK, RUMOURED, classify, is_upgrade
from worker.verification.tickets import merge_tickets

log = logging.getLogger("worker")

HTML_SOURCE_TYPES = ("artist_website", "promoter_website")


@dataclass
class EventChange:
    """A user-relevant change. Only emitted for events that are visible to users (not rumoured)."""
    kind: str                 # new_event | confirmed | status_changed
    event_id: Optional[str]
    artist_id: str
    city: str
    event_date: str
    confidence: str
    status: str


def _empty_stats() -> Dict[str, int]:
    return {"sources": 0, "unchanged": 0, "failed": 0, "candidates": 0, "events_new": 0,
            "events_existing": 0, "events_upgraded": 0, "events_status_changed": 0, "tickets_saved": 0, "past_skipped": 0}


def run(repo, fetcher: PoliteFetcher, *, now: dt.datetime, dry_run: bool = False,
        limit: int = config.DEFAULT_SOURCE_LIMIT, catalog_limit: int = config.DEFAULT_CATALOG_LIMIT,
        on_change: Optional[Callable[[EventChange], None]] = None) -> Dict[str, int]:
    stats = _empty_stats()
    tracked_ids = repo.tracked_artist_ids()
    artists: List[Dict[str, Any]] = repo.catalog_artists(tracked_ids)      # followed artists + the whole catalog
    if not artists:
        log.info("No artists in the catalog: nothing to do.")
        return stats
    by_id = {a["artist_id"]: a for a in artists}
    stamp = now.isoformat()

    def emit(kind: str, event_id: Optional[str], artist_id: str, cand, confidence: str, status: str) -> None:
        if on_change and confidence != RUMOURED:
            on_change(EventChange(kind, event_id, artist_id, cand.city, cand.event_date, confidence, status))

    def save_tickets(event_id: str, cand, confidence: str, event_confidence: str) -> None:
        """Ticket info only comes from non-rumoured sources and never from one weaker than the event's own."""
        if confidence == RUMOURED or RANK[confidence] < RANK[event_confidence]:
            return
        info = drop_late_moments(cand.tickets, cand.event_date) if cand.tickets else extract_ticket_info(cand.text, cand.event_date)
        if info.is_empty() and not cand.booking_url:
            return
        row = merge_tickets(repo.get_ticket(event_id) if event_id else None, info, cand.booking_url,
                            confidence == CONFIRMED, stamp)
        if row is None:
            return
        stats["tickets_saved"] += 1
        if not dry_run:
            repo.upsert_ticket(dict(row, event_id=event_id))

    if not dry_run:
        known = repo.source_urls()
        for a in artists:                                  # register official sites that are not sources yet
            if a.get("official_website") and a["official_website"] not in known:
                repo.ensure_source("artist_website", a["official_website"], a["artist_id"])

    for src in repo.sources_to_check(HTML_SOURCE_TYPES, tracked_ids, stamp, limit, catalog_limit):
        stats["sources"] += 1
        result = fetcher.fetch(src["source_url"])
        if result.status != OK:
            stats["failed"] += 1
            log.warning("%s -> %s (%s)", src["source_url"], result.status, result.detail)
            if not dry_run:
                repo.insert_log(src["source_id"], src["source_url"], None, "error")
                repo.update_source(src["source_id"], result.status, stamp)
            continue

        ref = "sha256:" + hashlib.sha256(result.text.encode("utf-8")).hexdigest() + "|v" + config.EXTRACTOR_VERSION
        if repo.last_content_ref(src["source_id"]) == ref:
            stats["unchanged"] += 1
            if not dry_run:
                repo.touch_verified(src["source_id"], stamp)
                repo.update_source(src["source_id"], "ok", stamp)
            continue

        for cand in extract_all(result.text, result.url, official_owner=bool(src.get("artist_id"))):
            if cand.event_date < (now - dt.timedelta(days=1)).date().isoformat():
                stats["past_skipped"] += 1             # never create or alert on shows that already happened
                continue
            stats["candidates"] += 1
            if src.get("artist_id"):
                owners = [Match(by_id[src["artist_id"]], False)] if src["artist_id"] in by_id else []
                owner_source = True
            else:
                owners = match_artists_detailed(cand.snippet, artists)
                owner_source = False
                if not owners and cand.event_name and src["source_type"] == "promoter_website" and not dry_run:
                    act_id = repo.ensure_act_artist(act_name(cand.event_name))   # a promoter's show by someone outside the catalog
                    if act_id:
                        owners = [Match({"artist_id": act_id, "artist_name": act_name(cand.event_name)}, False)]

            for m in owners:
                artist_id = m.artist["artist_id"]
                confidence = classify(src["source_type"], owner_source=owner_source, ambiguous_name=m.ambiguous)
                existing = repo.find_event(artist_id, cand.city, cand.event_date)

                if existing is None:
                    if cand.status != "scheduled":
                        continue                 # a cancellation notice for a show we never tracked
                    log.info("new %s: %s | %s | %s", confidence, m.artist["artist_name"], cand.city, cand.event_date)
                    if dry_run:
                        stats["events_new"] += 1
                        continue
                    created = repo.insert_event({
                        "artist_id": artist_id, "city": cand.city, "event_date": cand.event_date,
                        "venue": cand.venue, "event_name": cand.event_name, "booking_url": cand.booking_url, "source_id": src["source_id"],
                        "confidence": confidence, "status": "scheduled",
                        "first_seen_at": stamp, "detected_at": stamp,
                        "last_verified_at": stamp if confidence != RUMOURED else None,
                    })
                    stats["events_new" if created else "events_existing"] += 1
                    if created:
                        emit("new_event", created["event_id"], artist_id, cand, confidence, "scheduled")
                        save_tickets(created["event_id"], cand, confidence, confidence)
                    continue

                stats["events_existing"] += 1
                updates: Dict[str, Any] = {}
                new_conf = existing["confidence"]
                if is_upgrade(existing["confidence"], confidence):
                    new_conf = confidence
                    updates.update(confidence=confidence, source_id=src["source_id"])   # credit the better source
                    stats["events_upgraded"] += 1
                if RANK[confidence] > 0:
                    updates["last_verified_at"] = stamp
                if RANK[confidence] >= RANK[CONFIRMED]:           # official sources may fill in details we lack
                    for column, value in (("booking_url", cand.booking_url), ("venue", cand.venue), ("event_name", cand.event_name)):
                        if value and not existing.get(column):
                            updates[column] = value
                # Only an official source may cancel or postpone.
                status_changed = (confidence == CONFIRMED and cand.status != "scheduled"
                                  and existing["status"] != cand.status)
                if status_changed:
                    updates["status"] = cand.status
                    stats["events_status_changed"] += 1
                if updates and not dry_run:
                    repo.update_event(existing["event_id"], updates)
                if not dry_run and existing["status"] != "cancelled" and not status_changed:
                    save_tickets(existing["event_id"], cand, confidence, new_conf)
                if status_changed:
                    emit("status_changed", existing["event_id"], artist_id, cand, new_conf, cand.status)
                elif "confidence" in updates and new_conf == CONFIRMED:
                    emit("confirmed", existing["event_id"], artist_id, cand, new_conf, existing["status"])

        if not dry_run:
            repo.insert_log(src["source_id"], src["source_url"], ref, "processed")
            repo.update_source(src["source_id"], "ok", stamp)
    return stats

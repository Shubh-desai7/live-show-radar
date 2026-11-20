"""Publisher RSS pipeline: read each allowed news feed, match headlines against the whole artist catalog and create
UNCONFIRMED show reports.

Never creates a confirmed event, never touches an existing event (an official source may later upgrade a report through
the normal pipeline), and never alerts (alerts are for confirmed events only). robots.txt is honoured by the fetcher.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Dict, List

from worker.collectors.http import OK, PoliteFetcher
from worker.collectors.publisher_feeds import PUBLISHER_FEEDS
from worker.extractors.feeds import parse_feed
from worker.extractors.news import _plain, candidate_from_item
from worker.extractors.roundup import act_name, extract_roundup
from worker.matching.artists import match_artists_detailed
from worker.verification.classify import classify

log = logging.getLogger("worker")


def run_feeds(repo, fetcher: PoliteFetcher, catalog: List[Dict[str, Any]], *, now: dt.datetime, dry_run: bool = False,
              recheck_minutes: int = 55) -> Dict[str, int]:
    stats = {"feeds_checked": 0, "feed_items": 0, "feed_reports_new": 0, "feeds_failed": 0, "roundup_events_new": 0}
    stamp = now.isoformat()
    if not dry_run:
        known = repo.source_urls()
        for url in PUBLISHER_FEEDS:
            if url not in known:
                repo.ensure_source("publisher_rss", url, None)

    for src in repo.publisher_sources_due(stamp, recheck_minutes):
        stats["feeds_checked"] += 1
        res = fetcher.fetch(src["source_url"])                       # robots.txt honoured
        if res.status != OK:
            stats["feeds_failed"] += 1
            log.warning("feed %s -> %s (%s)", src["source_url"], res.status, res.detail)
            if not dry_run:
                repo.update_source(src["source_id"], res.status, stamp)
            continue
        for item in parse_feed(res.text):
            stats["feed_items"] += 1
            if item.content:
                _roundups(repo, catalog, item, now, stamp, dry_run, stats)
            for m in match_artists_detailed(_plain(item.title), catalog):
                cand = candidate_from_item(item, m.artist, now)
                if cand is None or repo.find_event(m.artist["artist_id"], cand.city, cand.event_date):
                    continue
                confidence = classify("publisher_rss", owner_source=False, ambiguous_name=cand.ambiguous_name)
                log.info("news report (%s): %s | %s | %s", confidence, m.artist["artist_name"], cand.city, cand.event_date)
                stats["feed_reports_new"] += 1
                if dry_run:
                    continue
                repo.insert_event({
                    "artist_id": m.artist["artist_id"], "city": cand.city, "event_date": cand.event_date,
                    "event_name": cand.title, "source_id": repo.article_source(cand.link, m.artist["artist_id"]),
                    "confidence": confidence, "status": "scheduled", "source_published_at": cand.published.isoformat(),
                    "first_seen_at": stamp, "detected_at": stamp})
        if not dry_run:
            repo.update_source(src["source_id"], "ok", stamp)
    return stats


def _roundups(repo, catalog: List[Dict[str, Any]], item, now: dt.datetime, stamp: str, dry_run: bool, stats: Dict[str, int]) -> None:
    """Festival/gig roundup articles: one report for the event itself (an 'act' named after it) plus one per catalog artist
    named in its lineup text. All Unconfirmed (or rumoured for ambiguous artist names); existing events are never touched."""
    for ev in extract_roundup(item.content, item.link, now.date()):
        targets = [(None, act_name(ev.name), False)]
        targets += [(m.artist["artist_id"], m.artist["artist_name"], m.ambiguous) for m in match_artists_detailed(ev.blurb, catalog)]
        for artist_id, label, ambiguous in targets:
            if dry_run:
                stats["roundup_events_new"] += 1
                continue
            if artist_id is None:
                artist_id = repo.ensure_act_artist(label)
                if artist_id is None:
                    continue
            if repo.find_event(artist_id, ev.city, ev.event_date):
                continue
            confidence = classify("publisher_rss", owner_source=False, ambiguous_name=ambiguous)
            log.info("roundup (%s): %s | %s | %s", confidence, label, ev.city, ev.event_date)
            stats["roundup_events_new"] += 1
            repo.insert_event({
                "artist_id": artist_id, "city": ev.city, "event_date": ev.event_date, "event_name": ev.name[:200], "venue": ev.venue,
                "booking_url": ev.link, "source_id": repo.article_source(item.link, artist_id), "confidence": confidence,
                "status": "scheduled", "source_published_at": item.published.isoformat() if item.published else None,
                "first_seen_at": stamp, "detected_at": stamp})

"""Publisher RSS pipeline: read each allowed news feed, match headlines against the whole artist catalog and create
UNCONFIRMED show reports.

Never creates a confirmed event, never touches an existing event (an official source may later upgrade a report through
the normal pipeline), and never alerts (alerts are for confirmed events only). robots.txt is honoured by the fetcher.
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from typing import Any, Dict, List, Optional

from worker.collectors.http import OK, PoliteFetcher
from worker.collectors.gdelt import RECHECK_MINUTES as GDELT_RECHECK, gdelt_urls, is_gdelt
from worker.collectors.publisher_feeds import PUBLISHER_FEEDS
from worker.extractors.feeds import parse_feed
from worker.extractors.news import _plain, candidate_from_item
from worker.extractors.roundup import act_name, extract_roundup
from worker.matching.artists import match_artists_detailed
from worker.stats import RunReport, SourceResult, Trace
from worker.verification.classify import classify

log = logging.getLogger("worker")


def run_feeds(repo, fetcher: PoliteFetcher, catalog: List[Dict[str, Any]], *, now: dt.datetime, dry_run: bool = False,
              recheck_minutes: int = 55, report: Optional[RunReport] = None, sleep=time.sleep) -> Dict[str, int]:
    report = report if report is not None else RunReport()
    stats = {"feeds_checked": 0, "feed_items": 0, "feed_reports_new": 0, "feeds_failed": 0, "roundup_events_new": 0}
    stamp = now.isoformat()
    if not dry_run:
        known = repo.source_urls()
        for url in list(PUBLISHER_FEEDS) + gdelt_urls():
            if url not in known:
                repo.ensure_source("publisher_rss", url, None)

    for src in repo.publisher_sources_due(stamp, recheck_minutes):
        if is_gdelt(src["source_url"]) and not _gdelt_due(src, now):
            continue                                                  # GDELT queries run at most every 6 hours
        stats["feeds_checked"] += 1
        report.counters["sources_attempted"] += 1
        res = fetcher.fetch(src["source_url"])                       # robots.txt honoured
        if is_gdelt(src["source_url"]) and res.status != OK and "429" in (res.detail or ""):
            sleep(30)                                                 # GDELT rate limit: one polite retry
            res = fetcher.fetch(src["source_url"])
        sres = SourceResult(src["source_id"], src["source_url"], res.status, res.detail)
        report.source_results.append(sres)
        trace = Trace()
        if res.status != OK:
            report.counters["sources_blocked" if res.status in ("blocked", "robots_disallowed") else "sources_failed"] += 1
            stats["feeds_failed"] += 1
            log.warning("feed %s -> %s (%s)", src["source_url"], res.status, res.detail)
            if not dry_run:
                repo.update_source(src["source_id"], res.status, stamp)
            continue
        report.counters["sources_fetched"] += 1
        report.counters["sources_new_content"] += 1
        for item in parse_feed(res.text):
            stats["feed_items"] += 1
            report.counters["feed_items"] += 1
            if item.content:
                _roundups(repo, catalog, item, now, stamp, dry_run, stats, trace, report)
            for m in match_artists_detailed(_plain(item.title), catalog):
                report.counters["artist_matches"] += 1
                cand = candidate_from_item(item, m.artist, now, trace)
                if cand is None or repo.find_event(m.artist["artist_id"], cand.city, cand.event_date):
                    continue
                confidence = classify("publisher_rss", owner_source=False, ambiguous_name=cand.ambiguous_name)
                log.info("news report (%s): %s | %s | %s", confidence, m.artist["artist_name"], cand.city, cand.event_date)
                stats["feed_reports_new"] += 1
                report.counters["candidates_extracted"] += 1
                report.counters["events_created_" + confidence] += 1
                sres.candidates += 1
                sres.events_new += 1
                if dry_run:
                    continue
                repo.insert_event({
                    "artist_id": m.artist["artist_id"], "city": cand.city, "event_date": cand.event_date,
                    "event_name": cand.title, "source_id": repo.article_source(cand.link, m.artist["artist_id"]),
                    "confidence": confidence, "status": "scheduled", "source_published_at": cand.published.isoformat(),
                    "first_seen_at": stamp, "detected_at": stamp})
        sres.rejected = report.add_rejections(src["source_id"], trace)
        if not dry_run:
            repo.update_source(src["source_id"], "ok", stamp)
    return stats


def _gdelt_due(src: Dict[str, Any], now: dt.datetime) -> bool:
    last = src.get("last_checked_at")
    if not last:
        return True
    try:
        return (now - dt.datetime.fromisoformat(str(last).replace("Z", "+00:00"))).total_seconds() >= GDELT_RECHECK * 60
    except ValueError:
        return True


def _roundups(repo, catalog: List[Dict[str, Any]], item, now: dt.datetime, stamp: str, dry_run: bool, stats: Dict[str, int],
              trace: Optional[Trace] = None, report: Optional[RunReport] = None) -> None:
    """Festival/gig roundup articles: one report for the event itself (an 'act' named after it) plus one per catalog artist
    named in its lineup text. All Unconfirmed (or rumoured for ambiguous artist names); existing events are never touched."""
    for ev in extract_roundup(item.content, item.link, now.date(), trace):
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
            if report is not None:
                report.counters["candidates_extracted"] += 1
            if repo.find_event(artist_id, ev.city, ev.event_date):
                if report is not None:
                    report.counters["duplicates_ignored"] += 1
                continue
            confidence = classify("publisher_rss", owner_source=False, ambiguous_name=ambiguous)
            if report is not None:
                report.counters["events_created_" + confidence] += 1
            log.info("roundup (%s): %s | %s | %s", confidence, label, ev.city, ev.event_date)
            stats["roundup_events_new"] += 1
            repo.insert_event({
                "artist_id": artist_id, "city": ev.city, "event_date": ev.event_date, "event_name": ev.name[:200], "venue": ev.venue,
                "booking_url": ev.link, "source_id": repo.article_source(item.link, artist_id), "confidence": confidence,
                "status": "scheduled", "source_published_at": item.published.isoformat() if item.published else None,
                "first_seen_at": stamp, "detected_at": stamp})

"""Entry point.

  python -m worker.main [discover] [--dry-run] [--limit N]   find events, create alerts, deliver due notifications
  python -m worker.main remind [--dry-run]                   schedule 24h/2h reminders, deliver due notifications

Designed for GitHub Actions cron (best effort, never exact or real-time): run `discover` a few times a day
and `remind` every ~15 minutes. Every run touches the database, which also keeps a free Supabase project awake.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys

from worker import config
from worker.collectors.http import PoliteFetcher
from worker.collectors.musicbrainz import MusicBrainzClient
from worker.diagnose import analyze
from worker.discovery.sites import discover_sites
from worker.collectors.jambase import JamBaseClient
from worker.feeds_pipeline import run_feeds
from worker.jambase_pipeline import run_jambase
from worker.database.client import SupabaseRest
from worker.database.repo import Repo
from worker.notifications import engine
from worker.notifications.telegram import TelegramClient
from worker.pipeline import run
from worker.stats import RunReport

log = logging.getLogger("worker")

WRITE_METHODS = {"insert_notification": True, "cancel_notifications": None, "update_notification": None,
                 "claim_notification": True, "unlink_chat": None}


class ReadOnlyRepo:
    """Dry-run wrapper: reads pass through, writes are swallowed."""
    def __init__(self, repo: Repo) -> None:
        self._repo = repo

    def __getattr__(self, name):
        if name in WRITE_METHODS:
            return lambda *a, **k: WRITE_METHODS[name]
        return getattr(self._repo, name)


def _telegram_or_none():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        log.warning("TELEGRAM_BOT_TOKEN not set: notifications are created but not delivered.")
        return None
    return TelegramClient(token)


def _trigger() -> str:
    ev = os.environ.get("GITHUB_EVENT_NAME", "")
    return "schedule" if ev == "schedule" else "manual" if ev == "workflow_dispatch" else "local"


def cmd_discover(args, repo: Repo, now: dt.datetime, report: RunReport) -> dict:
    directory = repo.user_directory()
    alerts = {"alerts_created": 0}
    fetcher = PoliteFetcher(allow_local=config.flag("WORKER_ALLOW_LOCAL"))

    def on_change(change) -> None:
        alerts["alerts_created"] += engine.create_event_alert(repo, directory, change, now)

    stats: dict = {}
    if not args.skip_sites:                       # find + verify official sites for artists that have none (bounded per run)
        stats.update(discover_sites(repo, MusicBrainzClient(), fetcher, repo.tracked_artist_ids(), now, dry_run=args.dry_run,
                                    limit_tracked=args.sites_tracked, limit_catalog=args.sites_catalog))
    stats.update(run(repo, fetcher, now=now, dry_run=args.dry_run, limit=args.limit, catalog_limit=args.catalog_limit,
                     on_change=None if args.dry_run else on_change, report=report))
    if not args.skip_feeds:                       # headline-level reports from allowed publisher feeds: Unconfirmed only
        stats.update(run_feeds(repo, fetcher, repo.catalog_artists(repo.tracked_artist_ids()), now=now, dry_run=args.dry_run, report=report))
    if not args.skip_feeds:                       # licensed event database (needs JAMBASE_API_KEY + JAMBASE_PLAN=developer to write)
        stats.update(run_jambase(repo, JamBaseClient(), repo.catalog_artists(repo.tracked_artist_ids()), now=now, dry_run=args.dry_run, report=report))
    stats.update(alerts)
    telegram = None if args.dry_run else _telegram_or_none()
    if telegram:
        stats.update(engine.deliver_due(repo, repo.user_directory(), telegram, now))
    return stats


def cmd_diagnose(args, repo: Repo, now: dt.datetime) -> dict:
    """Read-only: re-fetch sources (registered ones, or those listed in --urls) and report extraction results and rejections."""
    from collections import Counter
    fetcher = PoliteFetcher(allow_local=config.flag("WORKER_ALLOW_LOCAL"))
    catalog = repo.catalog_artists(repo.tracked_artist_ids())
    if args.urls:
        targets = json.load(open(args.urls))
    else:
        rows = repo.db.select("sources", {"select": "source_url,source_type,artist_id", "source_type": "in.(artist_website,promoter_website,publisher_rss)", "limit": "500"})
        names = {a["artist_id"]: a["artist_name"] for a in catalog}
        targets = [{"url": r["source_url"], "source_type": r["source_type"], "artist": names.get(r["artist_id"]), "feed": r["source_type"] == "publisher_rss"} for r in rows]
    results = []
    for t in targets[: args.limit]:
        r = analyze(fetcher, t["url"], source_type=t.get("source_type", "artist_website"), artist=t.get("artist"), catalog=catalog,
                    now=now, feed=bool(t.get("feed")))
        r.update({k: t[k] for k in ("name", "category") if k in t})
        results.append(r)
        print("%-9s %-62s events=%-2d rejected=%s" % ("ok" if r["accessible"] else r["fetch_status"][:9], r["url"][:62], len(r["events"]), r["rejections"] or "-"), flush=True)
    if args.json:
        json.dump(results, open(args.json, "w"), indent=1, default=str)
    reasons = Counter()
    for r in results:
        reasons.update(r["rejections"])
    return {"sources": len(results), "accessible": sum(r["accessible"] for r in results), "events": sum(len(r["events"]) for r in results),
            "rejection_reasons": dict(reasons)}


def cmd_remind(args, repo: Repo, now: dt.datetime) -> dict:
    directory = repo.user_directory()
    stats = engine.schedule_reminders(ReadOnlyRepo(repo) if args.dry_run else repo, directory, now)
    telegram = None if args.dry_run else _telegram_or_none()
    if telegram:
        stats.update(engine.deliver_due(repo, directory, telegram, now))
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Live Show Radar worker")
    sub = ap.add_subparsers(dest="command")
    d = sub.add_parser("discover", help="discovery + event alerts (default)")
    d.add_argument("--dry-run", action="store_true", help="fetch and extract but write nothing")
    d.add_argument("--limit", type=int, default=config.DEFAULT_SOURCE_LIMIT, help="max followed/promoter sources per run")
    d.add_argument("--skip-sites", action="store_true", help="skip automatic official-site discovery (MusicBrainz)")
    d.add_argument("--skip-feeds", action="store_true", help="skip publisher RSS feeds (unconfirmed news reports)")
    d.add_argument("--sites-tracked", type=int, default=10, help="followed artists whose official site is looked up per run")
    d.add_argument("--sites-catalog", type=int, default=8, help="other catalog artists whose official site is looked up per run")
    d.add_argument("--catalog-limit", type=int, default=config.DEFAULT_CATALOG_LIMIT, help="other catalog artists' pages re-read per run")
    g = sub.add_parser("diagnose", help="read-only replay of sources with rejection reasons (writes nothing)")
    g.add_argument("--urls", help="JSON file: [{url, source_type, artist, feed, name, category}, ...] instead of the registered sources")
    g.add_argument("--json", help="write the full results to this JSON file")
    g.add_argument("--limit", type=int, default=1000)
    r = sub.add_parser("remind", help="schedule reminders and deliver due notifications")
    r.add_argument("--dry-run", action="store_true", help="compute reminders but write/send nothing")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in ("discover", "remind", "diagnose", "-h", "--help")):
        argv.insert(0, "discover")                   # `python -m worker.main --dry-run` keeps working
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config.load_env_file()
    repo = Repo(SupabaseRest(config.require_env("NEXT_PUBLIC_SUPABASE_URL"), config.require_env("SUPABASE_SERVICE_ROLE_KEY")))
    now = dt.datetime.now(dt.timezone.utc)
    if args.command == "diagnose":
        print(json.dumps({"command": "diagnose", **cmd_diagnose(args, repo, now)}))
        return 0
    report = RunReport(command=args.command, trigger=_trigger())
    run_id = None if getattr(args, "dry_run", False) else repo.start_run(args.command, report.trigger)
    try:
        stats = cmd_remind(args, repo, now) if args.command == "remind" else cmd_discover(args, repo, now, report)
    except Exception as exc:                       # record the failure, then re-raise so CI shows it
        if run_id:
            repo.finish_run(run_id, False, report.summary(), type(exc).__name__ + ": " + str(exc)[:300])
        raise
    if run_id:
        summary = dict(report.summary(), **{k: v for k, v in stats.items() if isinstance(v, int)})
        repo.finish_run(run_id, True, summary)
        repo.save_source_results(run_id, report.source_results)
        stats["candidates_retained"] = repo.save_candidates(report.candidates)
        repo.prune_monitoring(now)
    elif report.reasons:
        stats["rejection_reasons"] = dict(report.reasons)
    print(json.dumps({"command": args.command, "dry_run": args.dry_run, **stats}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

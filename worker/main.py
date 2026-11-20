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
from worker.database.client import SupabaseRest
from worker.database.repo import Repo
from worker.notifications import engine
from worker.notifications.telegram import TelegramClient
from worker.pipeline import run

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


def cmd_discover(args, repo: Repo, now: dt.datetime) -> dict:
    directory = repo.user_directory()
    alerts = {"alerts_created": 0}

    def on_change(change) -> None:
        alerts["alerts_created"] += engine.create_event_alert(repo, directory, change, now)

    stats = run(repo, PoliteFetcher(allow_local=config.flag("WORKER_ALLOW_LOCAL")), now=now,
                dry_run=args.dry_run, limit=args.limit, on_change=None if args.dry_run else on_change)
    stats.update(alerts)
    telegram = None if args.dry_run else _telegram_or_none()
    if telegram:
        stats.update(engine.deliver_due(repo, repo.user_directory(), telegram, now))
    return stats


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
    d.add_argument("--limit", type=int, default=config.DEFAULT_SOURCE_LIMIT, help="max sources per run")
    r = sub.add_parser("remind", help="schedule reminders and deliver due notifications")
    r.add_argument("--dry-run", action="store_true", help="compute reminders but write/send nothing")
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in ("discover", "remind", "-h", "--help")):
        argv.insert(0, "discover")                   # `python -m worker.main --dry-run` keeps working
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config.load_env_file()
    repo = Repo(SupabaseRest(config.require_env("NEXT_PUBLIC_SUPABASE_URL"), config.require_env("SUPABASE_SERVICE_ROLE_KEY")))
    now = dt.datetime.now(dt.timezone.utc)
    stats = cmd_remind(args, repo, now) if args.command == "remind" else cmd_discover(args, repo, now)
    print(json.dumps({"command": args.command, "dry_run": args.dry_run, **stats}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Reminder + alert engine: schedule notifications from database state, then deliver what is due.

Design rules
* Scheduling is derived from state and idempotent (unique `idempotency_key`), so every run can safely re-run it.
* Reminders exist only for confirmed, scheduled events whose ticket timing is reliable (`tickets.timing_reliable`),
  at 24 h and 2 h before each moment (presale registration deadline, presale opening, general sale).
* A reminder whose time passed no more than CATCHUP_GRACE ago is still sent (cron delay); older ones are skipped.
* Every notification is re-validated at send time (still linked, still following, preference still on, moment still ahead).
* Delivery is at-least-once: the attempt counter is claimed first (optimistic lock); retries use backoff and are bounded.
* GitHub Actions cron is best effort: delivery is never exact or real-time.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from worker.notifications import messages
from worker.notifications.telegram import BLOCKED, FAILED, RETRY, SENT

log = logging.getLogger("worker")

REMINDER_OFFSETS = (1440, 120)                     # minutes before the moment
CATCHUP_GRACE = dt.timedelta(minutes=60)
MAX_ATTEMPTS = 5
BACKOFF_MINUTES = (5, 15, 45, 120)

# ticket column -> (notification type, preference flag)
MOMENTS = {
    "presale_registration_deadline": ("presale_registration", "presale_alerts"),
    "presale_opening": ("presale_opening", "presale_alerts"),
    "general_sale_opening": ("general_sale", "ticket_sale_alerts"),
}
TYPE_TO_COLUMN = {v[0]: k for k, v in MOMENTS.items()}
TYPE_TO_PREF = {v[0]: v[1] for v in MOMENTS.values()}
TYPE_TO_PREF.update({"new_event": "new_event_alerts", "event_update": "event_update_alerts",
                     "event_cancelled": "event_update_alerts"})
REMINDER_TYPES = set(TYPE_TO_COLUMN)


def _parse(iso: str) -> dt.datetime:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))


def eligible_users(directory: Dict[str, Dict[str, Any]], artist_id: str, city: Optional[str], pref: str) -> List[Dict[str, Any]]:
    """Linked users who follow the artist, track the event's city, and have the preference on."""
    if not city:
        return []
    return [u for u in directory.values()
            if artist_id in u["artist_ids"] and city.lower() in u["cities"] and u["prefs"].get(pref, False)]


# --------------------------------------------------------------------------- scheduling
def schedule_reminders(repo, directory: Dict[str, Dict[str, Any]], now: dt.datetime) -> Dict[str, int]:
    stats = {"reminders_scheduled": 0, "reminders_cancelled": 0}
    desired: Set[str] = set()
    for ev in repo.reminder_candidates(now.date().isoformat()):
        ticket = ev.get("ticket")
        if not ticket or not ticket.get("timing_reliable"):
            continue
        for column, (ntype, pref) in MOMENTS.items():
            moment_iso = ticket.get(column)
            if not moment_iso:
                continue
            moment = _parse(moment_iso)
            if moment <= now:
                continue
            for offset in REMINDER_OFFSETS:
                when = moment - dt.timedelta(minutes=offset)
                if when < now - CATCHUP_GRACE:
                    continue
                for user in eligible_users(directory, ev["artist_id"], ev.get("city"), pref):
                    key = "reminder:%s:%s:%d:%s:%d" % (ev["event_id"], ntype, offset, user["user_id"], int(moment.timestamp()))
                    desired.add(key)
                    created = repo.insert_notification({
                        "user_id": user["user_id"], "event_id": ev["event_id"], "notification_type": ntype,
                        "channel": "telegram", "reminder_offset_minutes": offset,
                        "scheduled_at": max(when, now).isoformat(), "idempotency_key": key})
                    stats["reminders_scheduled"] += 1 if created else 0
    # A moment moved, the event was cancelled, a user opted out...: pending reminders no longer wanted are cancelled.
    stale = [r["notification_id"] for r in repo.pending_reminders() if r["idempotency_key"] not in desired]
    if stale:
        repo.cancel_notifications(stale, "superseded")
        stats["reminders_cancelled"] = len(stale)
    return stats


def create_event_alert(repo, directory: Dict[str, Dict[str, Any]], change, now: dt.datetime) -> int:
    """Alerts for a pipeline EventChange. Only confirmed events trigger normal alerts."""
    if change.event_id is None or change.confidence != "confirmed":
        return 0
    if change.kind in ("new_event", "confirmed"):
        ntype, tag = "new_event", "new_event"
    elif change.kind == "status_changed":
        ntype = "event_cancelled" if change.status == "cancelled" else "event_update"
        tag = "%s:%s" % (ntype, change.status)
    else:
        return 0
    n = 0
    for user in eligible_users(directory, change.artist_id, change.city, TYPE_TO_PREF[ntype]):
        if repo.insert_notification({
                "user_id": user["user_id"], "event_id": change.event_id, "notification_type": ntype,
                "channel": "telegram", "scheduled_at": now.isoformat(),
                "idempotency_key": "%s:%s:%s" % (tag, change.event_id, user["user_id"])}):
            n += 1
    return n


# --------------------------------------------------------------------------- delivery
def _still_wanted(n: Dict[str, Any], user: Optional[Dict[str, Any]], ev: Optional[Dict[str, Any]], now: dt.datetime) -> Optional[str]:
    """None if the notification should still be sent, else the reason to cancel it."""
    if user is None:
        return "telegram not linked"
    if ev is None:
        return "event missing"
    ntype = n["notification_type"]
    if not user["prefs"].get(TYPE_TO_PREF[ntype], False):
        return "preference turned off"
    if ev["artist_id"] not in user["artist_ids"] or (ev.get("city") or "").lower() not in user["cities"]:
        return "no longer follows artist/city"
    if ev["confidence"] != "confirmed":
        return "event not confirmed"
    if ntype in REMINDER_TYPES:
        ticket = ev.get("ticket") or {}
        if ev["status"] != "scheduled" or not ticket.get("timing_reliable"):
            return "event changed or timing unverified"
        moment = ticket.get(TYPE_TO_COLUMN[ntype])
        if not moment or _parse(moment) <= now:
            return "moment passed"
    elif ntype == "new_event" and ev["status"] != "scheduled":
        return "event no longer scheduled"
    elif ntype == "event_cancelled" and ev["status"] != "cancelled":
        return "event not cancelled"
    elif ntype == "event_update" and ev["status"] == "scheduled":
        return "event back to scheduled"
    return None


def deliver_due(repo, directory: Dict[str, Dict[str, Any]], telegram, now: dt.datetime, limit: int = 100) -> Dict[str, int]:
    stats = {"notif_sent": 0, "notif_retried": 0, "notif_failed": 0, "notif_cancelled": 0, "notif_blocked": 0, "notif_skipped_race": 0}
    due = repo.due_notifications(now.isoformat(), limit)
    events = repo.events_by_ids(sorted({n["event_id"] for n in due if n.get("event_id")})) if due else {}
    for n in due:
        user, ev = directory.get(n["user_id"]), events.get(n.get("event_id"))
        reason = _still_wanted(n, user, ev, now)
        if reason:
            repo.update_notification(n["notification_id"], {"delivery_status": "cancelled", "last_error": reason})
            stats["notif_cancelled"] += 1
            continue
        if not repo.claim_notification(n["notification_id"], n["attempts"]):
            stats["notif_skipped_race"] += 1
            continue
        attempts = n["attempts"] + 1
        text = messages.render(n["notification_type"], dict(ev, artist_name=ev["artist_name"]), ev.get("ticket"), user["timezone"], now)
        result = telegram.send_message(user["chat_id"], text)
        if result.status == SENT:
            repo.update_notification(n["notification_id"], {"delivery_status": "sent", "sent_at": now.isoformat(), "last_error": None})
            stats["notif_sent"] += 1
        elif result.status == BLOCKED:
            repo.update_notification(n["notification_id"], {"delivery_status": "failed", "last_error": result.error or "blocked"})
            repo.unlink_chat(n["user_id"])                  # the user blocked the bot: stop trying this chat
            directory.pop(n["user_id"], None)
            stats["notif_blocked"] += 1
        elif result.status == RETRY and attempts < MAX_ATTEMPTS:
            wait = max(float(result.retry_after or 0) / 60, BACKOFF_MINUTES[min(attempts - 1, len(BACKOFF_MINUTES) - 1)])
            repo.update_notification(n["notification_id"], {"scheduled_at": (now + dt.timedelta(minutes=wait)).isoformat(),
                                                           "last_error": result.error})
            stats["notif_retried"] += 1
        else:
            repo.update_notification(n["notification_id"], {"delivery_status": "failed", "last_error": result.error or FAILED})
            stats["notif_failed"] += 1
    return stats

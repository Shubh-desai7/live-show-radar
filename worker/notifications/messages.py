"""Plain-text Telegram messages. No markup is used, so artist names / URLs from the database can't inject formatting.
Times are shown in the user's timezone (stored times are UTC)."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

FOOTER = "Live Show Radar doesn't sell tickets; you buy on the official site."
LABELS = {
    "presale_registration": ("Presale registration closes", "presale_registration_deadline"),
    "presale_opening": ("Presale opens", "presale_opening"),
    "general_sale": ("General sale opens", "general_sale_opening"),
}


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:  # unknown/invalid zone name or missing tz data
        return ZoneInfo("Asia/Kolkata")


def fmt_moment(iso: str, tz: str) -> str:
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(_zone(tz))
    hour = d.hour % 12 or 12
    return "%d %s %d, %d:%02d %s %s" % (d.day, d.strftime("%b"), d.year, hour, d.minute, "AM" if d.hour < 12 else "PM", d.tzname())


def fmt_event_date(date: Optional[str]) -> str:
    if not date:
        return "date to be announced"
    d = dt.date.fromisoformat(date)
    return "%s %d %s %d" % (d.strftime("%a"), d.day, d.strftime("%b"), d.year)


def fmt_remaining(moment_iso: str, now: dt.datetime) -> str:
    moment = dt.datetime.fromisoformat(moment_iso.replace("Z", "+00:00"))
    minutes = max(int(round((moment - now).total_seconds() / 60)), 1)
    if minutes < 90:
        return "in about %d minutes" % minutes
    hours = int(round(minutes / 60))
    return "in about %d hours" % hours if hours < 48 else "in about %d days" % int(round(hours / 24))


def _headline(ev: Dict[str, Any]) -> str:
    city = ev.get("city") or "city to be announced"
    return "%s: %s, %s" % (ev["artist_name"], city, fmt_event_date(ev.get("event_date")))


def render(ntype: str, ev: Dict[str, Any], ticket: Optional[Dict[str, Any]], tz: str, now: dt.datetime) -> str:
    link = (ticket or {}).get("booking_url") or ev.get("booking_url")
    lines = []
    if ntype in LABELS:
        label, col = LABELS[ntype]
        moment = (ticket or {})[col]
        lines.append("%s %s" % (label, fmt_remaining(moment, now)))
        lines += [_headline(ev), "%s: %s" % (label, fmt_moment(moment, tz))]
    elif ntype == "new_event":
        lines += ["New show announced (confirmed by an official source)", _headline(ev)]
        for key, (label, col) in LABELS.items():
            if (ticket or {}).get(col) and (ticket or {}).get("timing_reliable"):
                lines.append("%s: %s" % (label, fmt_moment(ticket[col], tz)))
    elif ntype == "event_cancelled":
        lines += ["Show cancelled", _headline(ev)]
    elif ntype == "event_update":
        lines += ["Show %s" % ev.get("status", "updated"), _headline(ev), "Check the official page for the new details."]
    else:
        raise ValueError("unknown notification type: " + ntype)
    if link:
        lines.append("Official booking link: " + link)
    elif ntype in ("new_event",) or ntype in LABELS:
        lines.append("No booking link has been published yet; check the official page.")
    lines.append(FOOTER)
    return "\n".join(lines)

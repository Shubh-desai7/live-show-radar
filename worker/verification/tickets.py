"""Merge freshly extracted ticket info into the stored `tickets` row. Pure, so it is easy to test."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional

from worker.extractors.tickets import GENERAL_SALE, PRESALE_OPENING, PRESALE_REGISTRATION, TicketInfo

MOMENT_FIELDS = (PRESALE_REGISTRATION, PRESALE_OPENING, GENERAL_SALE)


def _same_instant(a: Optional[str], b: Optional[str]) -> bool:
    if a is None or b is None:
        return a is b
    return dt.datetime.fromisoformat(a.replace("Z", "+00:00")) == dt.datetime.fromisoformat(b.replace("Z", "+00:00"))


def merge_tickets(existing: Optional[Dict[str, Any]], info: TicketInfo, booking_url: Optional[str],
                  official_source: bool, stamp: str) -> Optional[Dict[str, Any]]:
    """Row to upsert, or None when nothing changed.

    * A newly extracted value replaces the stored one; a missing value never erases a stored one.
    * early_bird_status 'unknown' never overwrites a known status.
    * timing_reliable is recomputed only when this extraction contains moments, and needs an official source.
    """
    old = existing or {}
    row: Dict[str, Any] = {}
    for k in MOMENT_FIELDS:
        m = info.moments.get(k)
        row[k] = m.at.isoformat() if m else old.get(k)
    row["early_bird_status"] = (info.early_bird_status if info.early_bird_status != "unknown"
                                else old.get("early_bird_status", "unknown"))
    row["booking_url"] = booking_url or old.get("booking_url")
    row["timing_reliable"] = (info.reliable and official_source) if info.moments else bool(old.get("timing_reliable", False))

    unchanged = (all(_same_instant(row[k], old.get(k)) for k in MOMENT_FIELDS)
                 and row["early_bird_status"] == old.get("early_bird_status", "unknown")
                 and row["booking_url"] == old.get("booking_url")
                 and row["timing_reliable"] == bool(old.get("timing_reliable", False)))
    if unchanged or (existing is None and all(v in (None, "unknown", False) for v in row.values())):
        return None
    row["last_updated_at"] = stamp
    return row

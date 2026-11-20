"""Worker-facing data access. The pipeline only talks to this interface (easy to fake in tests)."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from worker.database.client import DatabaseError, SupabaseRest


class Repo:
    def __init__(self, db: SupabaseRest) -> None:
        self.db = db

    def tracked_artists(self) -> List[Dict[str, Any]]:
        """Artists followed by at least one user."""
        ids = sorted({r["artist_id"] for r in self.db.select("user_artists", {"select": "artist_id"})})
        if not ids:
            return []
        return self.db.select("artists", {
            "select": "artist_id,artist_name,official_website",
            "artist_id": "in.(%s)" % ",".join(ids),
        })

    def ensure_source(self, source_type: str, source_url: str, artist_id: Optional[str]) -> None:
        self.db.insert("sources", {"source_type": source_type, "source_url": source_url, "artist_id": artist_id},
                       ignore_duplicates=True, on_conflict="source_url")

    def sources_to_check(self, types: Iterable[str], artist_ids: List[str], limit: int) -> List[Dict[str, Any]]:
        ids = ",".join(artist_ids)
        scope = "artist_id.is.null" + (",artist_id.in.(%s)" % ids if ids else "")
        return self.db.select("sources", {
            "select": "source_id,source_type,source_url,artist_id,access_status,last_checked_at",
            "source_type": "in.(%s)" % ",".join(types),
            "or": "(%s)" % scope,
            "order": "last_checked_at.asc.nullsfirst",
            "limit": str(limit),
        })

    def last_content_ref(self, source_id: str) -> Optional[str]:
        rows = self.db.select("raw_source_logs", {
            "select": "raw_content_reference", "source_id": "eq." + source_id,
            "processing_status": "eq.processed", "order": "collected_at.desc", "limit": "1",
        })
        return rows[0]["raw_content_reference"] if rows else None

    def insert_log(self, source_id: str, source_url: str, ref: Optional[str], status: str) -> None:
        self.db.insert("raw_source_logs", {"source_id": source_id, "source_url": source_url,
                                           "raw_content_reference": ref, "processing_status": status})

    def find_event(self, artist_id: str, city: str, event_date: str) -> Optional[Dict[str, Any]]:
        rows = self.db.select("events", {
            "select": "event_id,confidence,status,source_id,booking_url", "artist_id": "eq." + artist_id,
            "city": "ilike." + city.replace("%", "").replace("_", "\\_"),
            "event_date": "eq." + event_date, "limit": "1",
        })
        return rows[0] if rows else None

    def insert_event(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """The inserted row, or None if the unique dedupe index rejected a duplicate."""
        try:
            return self.db.insert("events", row)
        except DatabaseError as exc:
            if exc.status == 409:
                return None
            raise

    def update_source(self, source_id: str, access_status: str, checked_at: str) -> None:
        self.db.update("sources", {"source_id": "eq." + source_id},
                       {"access_status": access_status, "last_checked_at": checked_at})

    def update_event(self, event_id: str, values: Dict[str, Any]) -> None:
        self.db.update("events", {"event_id": "eq." + event_id}, values)

    def touch_verified(self, source_id: str, at: str) -> None:
        """The source is still up and unchanged: events it reported are still listed."""
        self.db.update("events", {"source_id": "eq." + source_id, "status": "eq.scheduled",
                                  "confidence": "neq.rumoured"}, {"last_verified_at": at})

    def get_ticket(self, event_id: str) -> Optional[Dict[str, Any]]:
        rows = self.db.select("tickets", {"select": "*", "event_id": "eq." + event_id, "limit": "1"})
        return rows[0] if rows else None

    def upsert_ticket(self, row: Dict[str, Any]) -> None:
        self.db.insert("tickets", row, merge_duplicates=True, on_conflict="event_id")

    # ------------------------------------------------------------------ notifications
    @staticmethod
    def _chunks(items: List[str], n: int = 80) -> Iterable[List[str]]:
        for i in range(0, len(items), n):
            yield items[i:i + n]

    @staticmethod
    def _one(v: Any) -> Optional[Dict[str, Any]]:
        return (v[0] if v else None) if isinstance(v, list) else v

    def user_directory(self) -> Dict[str, Dict[str, Any]]:
        """Users who can receive Telegram alerts: chat id, timezone, preferences, followed artists, cities."""
        profiles = self.db.select("profiles", {"select": "user_id,telegram_chat_id,timezone", "telegram_chat_id": "not.is.null"})
        users = {p["user_id"]: {"user_id": p["user_id"], "chat_id": p["telegram_chat_id"], "timezone": p["timezone"],
                                "prefs": {}, "artist_ids": set(), "cities": set()} for p in profiles}
        for chunk in self._chunks(list(users)):
            ids = "in.(%s)" % ",".join(chunk)
            for r in self.db.select("notification_preferences", {"select": "*", "user_id": ids}):
                users[r["user_id"]]["prefs"] = r
            for r in self.db.select("user_artists", {"select": "user_id,artist_id", "user_id": ids}):
                users[r["user_id"]]["artist_ids"].add(r["artist_id"])
            for r in self.db.select("user_cities", {"select": "user_id,city", "user_id": ids}):
                users[r["user_id"]]["cities"].add(r["city"].lower())
        return users

    _EVENT_SELECT = ("event_id,artist_id,city,event_date,confidence,status,booking_url,artists(artist_name),"
                     "tickets(presale_registration_deadline,presale_opening,general_sale_opening,booking_url,timing_reliable)")

    def _flatten_event(self, r: Dict[str, Any]) -> Dict[str, Any]:
        artist = self._one(r.pop("artists", None)) or {}
        ticket = self._one(r.pop("tickets", None))
        return dict(r, artist_name=artist.get("artist_name", "Unknown artist"), ticket=ticket)

    def reminder_candidates(self, today: str) -> List[Dict[str, Any]]:
        rows = self.db.select("events", {
            "select": self._EVENT_SELECT.replace("tickets(", "tickets!inner("),
            "confidence": "eq.confirmed", "status": "eq.scheduled", "event_date": "gte." + today,
            "tickets.timing_reliable": "eq.true"})
        return [self._flatten_event(r) for r in rows]

    def events_by_ids(self, ids: List[str]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for chunk in self._chunks(ids):
            for r in self.db.select("events", {"select": self._EVENT_SELECT, "event_id": "in.(%s)" % ",".join(chunk)}):
                out[r["event_id"]] = self._flatten_event(r)
        return out

    def insert_notification(self, row: Dict[str, Any]) -> bool:
        """True if created or revived; False if one with this idempotency key already exists in any other state.

        A previously *cancelled* notification (e.g. the user unlinked, then reconnected) is revived to pending,
        because its unique key would otherwise block the reminder forever. Sent / failed ones are never revived.
        """
        if self.db.insert("notifications", row, ignore_duplicates=True, on_conflict="idempotency_key") is not None:
            return True
        revived = self.db.update_returning(
            "notifications", {"idempotency_key": "eq." + row["idempotency_key"], "delivery_status": "eq.cancelled"},
            {"delivery_status": "pending", "scheduled_at": row["scheduled_at"], "attempts": 0, "last_error": None})
        return bool(revived)

    def pending_reminders(self) -> List[Dict[str, Any]]:
        return self.db.select("notifications", {
            "select": "notification_id,idempotency_key", "delivery_status": "eq.pending",
            "notification_type": "in.(presale_registration,presale_opening,general_sale)"})

    def cancel_notifications(self, ids: List[str], reason: str) -> None:
        for chunk in self._chunks(ids):
            self.db.update("notifications", {"notification_id": "in.(%s)" % ",".join(chunk), "delivery_status": "eq.pending"},
                           {"delivery_status": "cancelled", "last_error": reason})

    def due_notifications(self, now_iso: str, limit: int) -> List[Dict[str, Any]]:
        return self.db.select("notifications", {
            "select": "notification_id,user_id,event_id,notification_type,reminder_offset_minutes,scheduled_at,attempts",
            "delivery_status": "eq.pending", "scheduled_at": "lte." + now_iso,
            "order": "scheduled_at.asc", "limit": str(limit)})

    def claim_notification(self, notification_id: str, attempts: int) -> bool:
        """Optimistic lock: only one worker can move attempts from N to N+1."""
        rows = self.db.update_returning("notifications", {
            "notification_id": "eq." + notification_id, "delivery_status": "eq.pending", "attempts": "eq.%d" % attempts},
            {"attempts": attempts + 1})
        return bool(rows)

    def update_notification(self, notification_id: str, values: Dict[str, Any]) -> None:
        self.db.update("notifications", {"notification_id": "eq." + notification_id}, values)

    def unlink_chat(self, user_id: str) -> None:
        self.db.update("profiles", {"user_id": "eq." + user_id}, {"telegram_chat_id": None})

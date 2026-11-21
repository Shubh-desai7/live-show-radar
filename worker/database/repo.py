"""Worker-facing data access. The pipeline only talks to this interface (easy to fake in tests)."""
from __future__ import annotations

import datetime as dt
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
            "select": "event_id,confidence,status,source_id,booking_url,venue,event_name", "artist_id": "eq." + artist_id,
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

    # ------------------------------------------------------------------ catalog + site discovery
    def tracked_artist_ids(self) -> List[str]:
        return sorted({r["artist_id"] for r in self.db.select("user_artists", {"select": "artist_id"})})

    def catalog_artists(self, tracked_ids: List[str]) -> List[Dict[str, Any]]:
        """Every featured (catalog) artist plus any followed artist: the set shows are matched against."""
        rows = self.db.select("artists", {"select": "artist_id,artist_name,official_website,metadata", "featured": "is.true", "limit": "2000"})
        have = {r["artist_id"] for r in rows}
        missing = [i for i in tracked_ids if i not in have]
        for chunk in self._chunks(missing):
            rows += self.db.select("artists", {"select": "artist_id,artist_name,official_website,metadata", "artist_id": "in.(%s)" % ",".join(chunk)})
        return rows

    def source_urls(self) -> set:
        return {r["source_url"] for r in self.db.select("sources", {"select": "source_url", "limit": "5000"})}

    def sources_to_check(self, types: Iterable[str], tracked_ids: List[str], now_iso: str, tier1_limit: int,
                         tier2_limit: int, recheck_minutes: int = 25) -> List[Dict[str, Any]]:
        """Tier 1: promoter pages and followed artists' pages, at most every `recheck_minutes`.
        Tier 2: other catalog artists' pages, at most daily, a few per run (so catalog shows are already fetched when someone follows)."""
        now = dt.datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        fresh_after = (now - dt.timedelta(minutes=recheck_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        daily_after = (now - dt.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cols = "source_id,source_type,source_url,artist_id,access_status,last_checked_at"
        scope = "artist_id.is.null" + (",artist_id.in.(%s)" % ",".join(tracked_ids) if tracked_ids else "")
        t1 = self.db.select("sources", {
            "select": cols, "source_type": "in.(%s)" % ",".join(types),
            "and": "(or(%s),or(last_checked_at.is.null,last_checked_at.lt.%s))" % (scope, fresh_after),
            "order": "last_checked_at.asc.nullsfirst", "limit": str(tier1_limit)})
        params = {"select": cols, "source_type": "in.(%s)" % ",".join(types), "artist_id": "not.is.null",
                  "or": "(last_checked_at.is.null,last_checked_at.lt.%s)" % daily_after,
                  "order": "last_checked_at.asc.nullsfirst", "limit": str(tier2_limit)}
        if tracked_ids:
            params["artist_id"] = "not.in.(%s)" % ",".join(tracked_ids)
        t2 = self.db.select("sources", params) if tier2_limit > 0 else []
        seen = {s["source_id"] for s in t1}
        return t1 + [s for s in t2 if s["source_id"] not in seen]

    def artists_needing_site(self, tracked_ids: List[str], now_z: str, limit_tracked: int, limit_catalog: int) -> List[Dict[str, Any]]:
        """Artists with no official site on file whose discovery is not waiting out a retry window. Followed artists first."""
        retry = "(metadata->>site_retry_after.is.null,metadata->>site_retry_after.lt.%s)" % now_z
        out: List[Dict[str, Any]] = []
        if tracked_ids and limit_tracked > 0:
            out += self.db.select("artists", {"select": "artist_id,artist_name,metadata", "official_website": "is.null",
                                              "artist_id": "in.(%s)" % ",".join(tracked_ids), "or": retry, "limit": str(limit_tracked)})
        if limit_catalog > 0:
            params = {"select": "artist_id,artist_name,metadata", "official_website": "is.null", "featured": "is.true",
                      "or": retry, "order": "featured_rank.asc.nullslast", "limit": str(limit_catalog)}
            if tracked_ids:
                params["artist_id"] = "not.in.(%s)" % ",".join(tracked_ids)
            out += self.db.select("artists", params)
        return out

    def save_site_result(self, artist: Dict[str, Any], d, now: dt.datetime) -> None:
        meta = dict(artist.get("metadata") or {})
        meta.update(site_status=d.status, site_detail=(d.detail or "")[:120],
                    site_checked_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    site_retry_after=(now + dt.timedelta(days=d.retry_days)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        values: Dict[str, Any] = {"metadata": meta}
        if d.status == "ok":
            values["official_website"] = d.official_url
        self.db.update("artists", {"artist_id": "eq." + artist["artist_id"]}, values)
        if d.status == "ok":
            for url in d.source_urls:
                self.ensure_source("artist_website", url, artist["artist_id"])

    # ------------------------------------------------------------------ publisher RSS feeds (unconfirmed reports)
    def publisher_sources_due(self, now_iso: str, recheck_minutes: int) -> List[Dict[str, Any]]:
        now = dt.datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        cutoff = (now - dt.timedelta(minutes=recheck_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.db.select("sources", {
            "select": "source_id,source_url,last_checked_at", "source_type": "eq.publisher_rss", "artist_id": "is.null",
            "or": "(last_checked_at.is.null,last_checked_at.lt.%s)" % cutoff, "order": "last_checked_at.asc.nullsfirst", "limit": "50"})

    def article_source(self, url: str, artist_id: str) -> Optional[str]:
        """One `sources` row per article that produced an event, so the event page can link the article."""
        row = self.db.insert("sources", {"source_type": "publisher_rss", "source_url": url, "artist_id": artist_id,
                                         "access_status": "ok"}, ignore_duplicates=True, on_conflict="source_url")
        if row:
            return row["source_id"]
        found = self.db.select("sources", {"select": "source_id", "source_url": "eq." + url, "limit": "1"})
        return found[0]["source_id"] if found else None

    # ------------------------------------------------------------------ "acts": festivals / events without a catalog artist
    def ensure_act_artist(self, name: str) -> Optional[str]:
        """Find-or-create a non-catalog `artists` row (e.g. a festival) so shows by anyone can be stored."""
        like = "ilike." + name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        found = self.db.select("artists", {"select": "artist_id", "artist_name": like, "limit": "1"})
        if found:
            return found[0]["artist_id"]
        try:
            row = self.db.insert("artists", {"artist_name": name, "metadata": {"origin": "act"}})
            return row["artist_id"] if row else None
        except DatabaseError as exc:
            if exc.status != 409:
                raise
            again = self.db.select("artists", {"select": "artist_id", "artist_name": like, "limit": "1"})
            return again[0]["artist_id"] if again else None


    # ------------------------------------------------------------------ monitoring
    def start_run(self, command: str, trigger: str) -> Optional[str]:
        row = self.db.insert("discovery_runs", {"command": command, "trigger": trigger})
        return row["run_id"] if row else None

    def finish_run(self, run_id: str, ok: bool, stats: Dict[str, Any], error: Optional[str] = None) -> None:
        self.db.update("discovery_runs", {"run_id": "eq." + run_id},
                       {"finished_at": dt.datetime.now(dt.timezone.utc).isoformat(), "ok": ok, "stats": stats, "error": (error or None)})

    def save_source_results(self, run_id: str, results: List[Any]) -> None:
        for chunk in self._chunks(list(range(len(results))), 100):
            rows = [{"run_id": run_id, "source_id": results[i].source_id, "source_url": results[i].source_url[:500],
                     "status": results[i].status, "detail": (results[i].detail or "")[:200], "candidates": results[i].candidates,
                     "rejected": results[i].rejected, "events_new": results[i].events_new, "duration_ms": results[i].duration_ms}
                    for i in chunk]
            if rows:
                self.db.insert("discovery_source_results", rows)  # type: ignore[arg-type]

    def save_candidates(self, pairs: List[Any]) -> int:
        """Keep rejected / incomplete candidates (deduplicated per source+content). Already-known ones just get last_seen_at."""
        saved = 0
        by_source: Dict[Optional[str], List[Any]] = {}
        for source_id, r in pairs:
            by_source.setdefault(source_id, []).append(r)
        for source_id, items in by_source.items():
            if source_id is None:
                continue
            known = {x["content_key"] for x in self.db.select("event_candidates", {"select": "content_key", "source_id": "eq." + source_id, "limit": "2000"})}
            fresh, seen_keys = [], []
            for r in items:
                (seen_keys if r.key() in known else fresh).append(r)
            if seen_keys:
                self.db.update("event_candidates", {"source_id": "eq." + source_id, "content_key": "in.(%s)" % ",".join(r.key() for r in seen_keys)},
                               {"last_seen_at": dt.datetime.now(dt.timezone.utc).isoformat()})
            rows = [{"source_id": source_id, "stage": r.stage, "reason": r.reason, "detail": r.detail[:200] or None, "artist_hint": r.artist_hint,
                     "event_name": (r.event_name or "")[:200] or None, "city_hint": (r.city_hint or "")[:120] or None,
                     "date_hint": (r.date_hint or "")[:60] or None, "venue": (r.venue or "")[:200] or None, "booking_url": r.booking_url,
                     "snippet": r.snippet[:300] or None, "content_key": r.key()} for r in fresh]
            seen_new = set()
            rows = [x for x in rows if not (x["content_key"] in seen_new or seen_new.add(x["content_key"]))]
            if rows:
                self.db.insert("event_candidates", rows)  # type: ignore[arg-type]
                saved += len(rows)
        return saved

    def prune_monitoring(self, now: dt.datetime) -> None:
        self.db.delete_where("discovery_runs", {"started_at": "lt." + (now - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")})
        self.db.delete_where("event_candidates", {"last_seen_at": "lt." + (now - dt.timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ")})

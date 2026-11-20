import datetime as dt

from worker.notifications import engine
from worker.notifications.telegram import BLOCKED, FAILED, RETRY, SENT, SendResult
from worker.pipeline import EventChange

NOW = dt.datetime(2026, 12, 1, 6, 0, tzinfo=dt.timezone.utc)
H = dt.timedelta(hours=1)


def iso(d): return d.isoformat()


def user(uid="u1", chat=111, artists=("a1",), cities=("bengaluru",), **prefs):
    p = {"new_event_alerts": True, "presale_alerts": True, "ticket_sale_alerts": True, "event_update_alerts": True}
    p.update(prefs)
    return {"user_id": uid, "chat_id": chat, "timezone": "Asia/Kolkata", "prefs": p, "artist_ids": set(artists), "cities": set(cities)}


def event(eid="e1", moment=NOW + 30 * H, column="general_sale_opening", reliable=True, **kw):
    t = {"presale_registration_deadline": None, "presale_opening": None, "general_sale_opening": None,
         "booking_url": None, "timing_reliable": reliable}
    t[column] = iso(moment)
    e = {"event_id": eid, "artist_id": "a1", "artist_name": "Nucleya", "city": "Bengaluru", "event_date": "2027-02-01",
         "confidence": "confirmed", "status": "scheduled", "booking_url": None, "ticket": t}
    e.update(kw)
    return e


class Repo:
    def __init__(self, events=()):
        self.events = {e["event_id"]: e for e in events}
        self.notes, self.unlinked = {}, []

    def reminder_candidates(self, today): return [e for e in self.events.values() if e["confidence"] == "confirmed" and e["status"] == "scheduled" and e["ticket"] and e["ticket"]["timing_reliable"]]
    def events_by_ids(self, ids): return {i: self.events[i] for i in ids if i in self.events}

    def insert_notification(self, row):
        same = [n for n in self.notes.values() if n["idempotency_key"] == row["idempotency_key"]]
        if same:                                            # mirrors Repo: only cancelled rows are revived
            if same[0]["delivery_status"] != "cancelled":
                return False
            same[0].update(delivery_status="pending", scheduled_at=row["scheduled_at"], attempts=0, last_error=None)
            return True
        nid = "n%d" % (len(self.notes) + 1)
        self.notes[nid] = dict(row, notification_id=nid, delivery_status="pending", attempts=0, last_error=None, sent_at=None)
        return True

    def pending_reminders(self):
        return [{"notification_id": i, "idempotency_key": n["idempotency_key"]} for i, n in self.notes.items()
                if n["delivery_status"] == "pending" and n["notification_type"] in engine.REMINDER_TYPES]

    def cancel_notifications(self, ids, reason):
        for i in ids:
            self.notes[i].update(delivery_status="cancelled", last_error=reason)

    def due_notifications(self, now_iso, limit):
        return [dict(n) for n in self.notes.values() if n["delivery_status"] == "pending" and n["scheduled_at"] <= now_iso][:limit]   # snapshot, like a DB read

    def claim_notification(self, nid, attempts):
        if self.notes[nid]["attempts"] != attempts or self.notes[nid]["delivery_status"] != "pending":
            return False
        self.notes[nid]["attempts"] += 1
        return True

    def update_notification(self, nid, values): self.notes[nid].update(values)
    def unlink_chat(self, uid): self.unlinked.append(uid)


class Tg:
    def __init__(self, *results): self.results, self.sent = list(results), []
    def send_message(self, chat, text):
        self.sent.append((chat, text))
        return self.results.pop(0) if self.results else SendResult(SENT)


def directory(*users): return {u["user_id"]: u for u in users}
def by_type(repo): return sorted((n["notification_type"], n.get("reminder_offset_minutes")) for n in repo.notes.values())


# ------------------------------------------------------------------ scheduling
def test_schedules_24h_and_2h_reminders_in_utc_before_a_reliable_moment():
    repo = Repo([event(moment=NOW + 30 * H)])
    engine.schedule_reminders(repo, directory(user()), NOW)
    times = {n["reminder_offset_minutes"]: n["scheduled_at"] for n in repo.notes.values()}
    assert times == {1440: iso(NOW + 6 * H), 120: iso(NOW + 28 * H)}
    assert all(n["channel"] == "telegram" and n["notification_type"] == "general_sale" for n in repo.notes.values())


def test_rerun_never_duplicates():
    repo = Repo([event()])
    d = directory(user())
    engine.schedule_reminders(repo, d, NOW)
    stats = engine.schedule_reminders(repo, d, NOW + H)
    assert len(repo.notes) == 2 and stats["reminders_scheduled"] == 0


def test_only_the_still_future_offsets_are_scheduled_and_stale_ones_skipped():
    repo = Repo([event(moment=NOW + 10 * H)])             # 24h mark passed 14h ago (beyond grace): skipped
    engine.schedule_reminders(repo, directory(user()), NOW)
    assert by_type(repo) == [("general_sale", 120)]


def test_recently_missed_reminder_is_sent_late_within_grace():
    repo = Repo([event(moment=NOW + 2 * H - dt.timedelta(minutes=30))])   # 2h mark was 30 min ago
    engine.schedule_reminders(repo, directory(user()), NOW)
    n = next(iter(repo.notes.values()))
    assert n["reminder_offset_minutes"] == 120 and n["scheduled_at"] == iso(NOW)


def test_past_moments_unreliable_timing_and_unconfirmed_events_get_nothing():
    repo = Repo([event("e1", moment=NOW - H), event("e2", reliable=False), event("e3", confidence="unconfirmed"),
                 event("e4", status="cancelled")])
    engine.schedule_reminders(repo, directory(user()), NOW)
    assert repo.notes == {}


def test_filters_by_followed_artist_city_preference_and_telegram_link():
    repo = Repo([event(column="presale_opening")])
    d = directory(user("u1"), user("u2", artists=("other",)), user("u3", cities=("pune",)), user("u4", presale_alerts=False))
    engine.schedule_reminders(repo, d, NOW)
    assert {n["user_id"] for n in repo.notes.values()} == {"u1"}      # users without a chat are not in the directory at all


def test_each_moment_type_uses_its_own_preference():
    ev = event(column="general_sale_opening")
    repo = Repo([ev])
    engine.schedule_reminders(repo, directory(user(ticket_sale_alerts=False)), NOW)
    assert repo.notes == {}


def test_moved_moment_cancels_old_reminders_and_schedules_new_ones():
    ev = event(moment=NOW + 30 * H)
    repo = Repo([ev])
    d = directory(user())
    engine.schedule_reminders(repo, d, NOW)
    ev["ticket"]["general_sale_opening"] = iso(NOW + 54 * H)
    stats = engine.schedule_reminders(repo, d, NOW)
    states = sorted((n["delivery_status"]) for n in repo.notes.values())
    assert states == ["cancelled", "cancelled", "pending", "pending"] and stats["reminders_cancelled"] == 2


def test_cancelled_event_cancels_its_pending_reminders():
    ev = event()
    repo = Repo([ev])
    d = directory(user())
    engine.schedule_reminders(repo, d, NOW)
    ev["status"] = "cancelled"
    engine.schedule_reminders(repo, d, NOW)
    assert {n["delivery_status"] for n in repo.notes.values()} == {"cancelled"}


# ------------------------------------------------------------------ event alerts
def change(kind="new_event", confidence="confirmed", status="scheduled"):
    return EventChange(kind, "e1", "a1", "Bengaluru", "2027-02-01", confidence, status)


def test_new_confirmed_event_alerts_matching_users_once():
    repo = Repo()
    d = directory(user("u1"), user("u2", new_event_alerts=False), user("u3", cities=("pune",)))
    assert engine.create_event_alert(repo, d, change(), NOW) == 1
    assert engine.create_event_alert(repo, d, change("confirmed"), NOW) == 0          # same key: no duplicate
    assert by_type(repo) == [("new_event", None)]


def test_unconfirmed_changes_never_alert_and_cancellation_uses_update_preference():
    repo = Repo()
    assert engine.create_event_alert(repo, directory(user()), change(confidence="unconfirmed"), NOW) == 0
    engine.create_event_alert(repo, directory(user(event_update_alerts=False)), change("status_changed", status="cancelled"), NOW)
    assert repo.notes == {}
    engine.create_event_alert(repo, directory(user()), change("status_changed", status="cancelled"), NOW)
    assert by_type(repo) == [("event_cancelled", None)]


# ------------------------------------------------------------------ delivery
def scheduled(repo, d, ev=None):
    engine.schedule_reminders(repo, d, NOW)
    return repo


def test_due_reminder_is_sent_marked_sent_and_not_resent():
    repo = Repo([event(moment=NOW + 2 * H - dt.timedelta(minutes=5))])
    d, tg = directory(user()), Tg()
    engine.schedule_reminders(repo, d, NOW)
    stats = engine.deliver_due(repo, d, tg, NOW)
    assert stats["notif_sent"] == 1 and tg.sent[0][0] == 111 and "General sale opens in about 2 hours" in tg.sent[0][1]
    sent = [n for n in repo.notes.values() if n["delivery_status"] == "sent"]
    assert len(sent) == 1 and sent[0]["sent_at"] == iso(NOW)
    assert engine.deliver_due(repo, d, tg, NOW)["notif_sent"] == 0


def test_retry_uses_backoff_then_gives_up_after_max_attempts():
    repo = Repo([event(moment=NOW + 24 * H - dt.timedelta(minutes=5))])       # the 24h reminder is due now
    d = directory(user())
    engine.schedule_reminders(repo, d, NOW)
    tg = Tg(*[SendResult(RETRY, error="HTTP 502")] * 10)
    n = next(x for x in repo.notes.values() if x["reminder_offset_minutes"] == 1440)
    t = NOW
    for attempt in range(1, engine.MAX_ATTEMPTS + 1):
        stats = engine.deliver_due(repo, d, tg, t)
        if attempt < engine.MAX_ATTEMPTS:
            assert stats["notif_retried"] == 1 and n["delivery_status"] == "pending" and n["scheduled_at"] > iso(t)
            t = dt.datetime.fromisoformat(n["scheduled_at"])
    assert n["delivery_status"] == "failed" and n["attempts"] == engine.MAX_ATTEMPTS and len(tg.sent) == engine.MAX_ATTEMPTS


def test_reminder_is_dropped_not_sent_late_once_its_moment_has_passed_during_retries():
    repo = Repo([event(moment=NOW + 2 * H - dt.timedelta(minutes=5))])
    d = directory(user())
    engine.schedule_reminders(repo, d, NOW)
    engine.deliver_due(repo, d, Tg(SendResult(RETRY, error="HTTP 502")), NOW)
    later = NOW + 3 * H
    stats = engine.deliver_due(repo, d, Tg(), later)
    assert stats["notif_cancelled"] == 1 and stats["notif_sent"] == 0


def test_telegram_rate_limit_hint_is_respected():
    repo = Repo([event(moment=NOW + 2 * H - dt.timedelta(minutes=5))])
    d = directory(user())
    engine.schedule_reminders(repo, d, NOW)
    engine.deliver_due(repo, d, Tg(SendResult(RETRY, retry_after=1800.0, error="rate limited")), NOW)
    n = next(iter(repo.notes.values()))
    assert n["scheduled_at"] >= iso(NOW + dt.timedelta(minutes=30))


def test_blocked_bot_unlinks_the_chat_and_fails_the_notification():
    repo = Repo([event(moment=NOW + 2 * H - dt.timedelta(minutes=5))])
    d = directory(user())
    engine.schedule_reminders(repo, d, NOW)
    stats = engine.deliver_due(repo, d, Tg(SendResult(BLOCKED, error="HTTP 403")), NOW)
    assert stats["notif_blocked"] == 1 and repo.unlinked == ["u1"] and "u1" not in d


def test_permanent_failure_is_not_retried():
    repo = Repo([event(moment=NOW + 2 * H - dt.timedelta(minutes=5))])
    d = directory(user())
    engine.schedule_reminders(repo, d, NOW)
    assert engine.deliver_due(repo, d, Tg(SendResult(FAILED, error="HTTP 400")), NOW)["notif_failed"] == 1


def test_send_time_revalidation_cancels_instead_of_sending():
    base = lambda: Repo([event(moment=NOW + 2 * H - dt.timedelta(minutes=5))])
    cases = {
        "unlinked": lambda r, d: d.clear(),
        "pref off": lambda r, d: d["u1"]["prefs"].update(ticket_sale_alerts=False),
        "unfollowed": lambda r, d: d["u1"]["artist_ids"].clear(),
        "event cancelled": lambda r, d: r.events["e1"].update(status="cancelled"),
        "timing no longer reliable": lambda r, d: r.events["e1"]["ticket"].update(timing_reliable=False),
        "moment passed": lambda r, d: r.events["e1"]["ticket"].update(general_sale_opening=iso(NOW - H)),
    }
    for name, mutate in cases.items():
        repo, d, tg = base(), directory(user()), Tg()
        engine.schedule_reminders(repo, d, NOW)
        mutate(repo, d)
        stats = engine.deliver_due(repo, d, tg, NOW)
        assert tg.sent == [] and stats["notif_cancelled"] == 1, name


def test_losing_the_claim_race_sends_nothing():
    repo = Repo([event(moment=NOW + 2 * H - dt.timedelta(minutes=5))])
    d, tg = directory(user()), Tg()
    engine.schedule_reminders(repo, d, NOW)
    orig = repo.due_notifications
    def due_then_lose_race(now_iso, limit):
        rows = orig(now_iso, limit)
        repo.claim_notification("n1", 0)                   # another worker claims it right after our read
        return rows
    repo.due_notifications = due_then_lose_race
    assert engine.deliver_due(repo, d, tg, NOW)["notif_skipped_race"] == 1 and tg.sent == []


def test_event_alert_is_delivered_with_cancellation_text():
    ev = event(status="cancelled")
    repo = Repo([ev])
    d, tg = directory(user()), Tg()
    engine.create_event_alert(repo, d, change("status_changed", status="cancelled"), NOW)
    assert engine.deliver_due(repo, d, tg, NOW)["notif_sent"] == 1 and tg.sent[0][1].startswith("Show cancelled")


def test_reminders_return_after_unlink_then_relink_but_sent_ones_never_repeat():
    repo = Repo([event(moment=NOW + 30 * H)])
    u = user()
    engine.schedule_reminders(repo, directory(u), NOW)
    engine.schedule_reminders(repo, {}, NOW)                                # user unlinked: reminders cancelled
    assert {n["delivery_status"] for n in repo.notes.values()} == {"cancelled"}
    stats = engine.schedule_reminders(repo, directory(u), NOW)              # reconnected
    assert {n["delivery_status"] for n in repo.notes.values()} == {"pending"} and stats["reminders_scheduled"] == 2
    first = next(n for n in repo.notes.values() if n["reminder_offset_minutes"] == 1440)
    first["delivery_status"] = "sent"
    assert engine.schedule_reminders(repo, directory(u), NOW)["reminders_scheduled"] == 0
    assert first["delivery_status"] == "sent"

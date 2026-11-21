import datetime as dt

from worker.collectors.jambase import JamBaseClient, SOURCE_URL, parse_event
from worker.jambase_pipeline import run_jambase

NOW = dt.datetime(2026, 11, 21, 12, tzinfo=dt.timezone.utc)


def ev(**kw):
    e = {"identifier": "jambase:1", "name": "Diljit Dosanjh at Mahalaxmi Race Course", "startDate": "2026-11-27T16:00:00",
         "location": {"name": "Mahalaxmi Race Course", "address": {"addressLocality": {"name": "Mumbai"}}},
         "performer": [{"name": "Diljit Dosanjh"}], "offers": [{"url": "https://tickets.example/x?a=1"}], "url": "https://www.jambase.com/show/1",
         "dateModified": "2026-11-20T10:00:00Z"}
    e.update(kw)
    return e


class Resp:
    def __init__(self, code=200, body=None): self.status_code, self._b = code, body or {}
    def json(self): return self._b


class Session:
    def __init__(self, *resps): self.resps, self.calls = list(resps), []
    def get(self, url, **kw): self.calls.append(kw["params"]); return self.resps.pop(0)


class Repo:
    def __init__(self, existing=(), last=None):
        self.events, self.acts, self.existing, self.updates, self.last = [], [], list(existing), [], last
    def ensure_source(self, *a): pass
    def jambase_source(self): return {"source_id": "s1", "last_checked_at": self.last}
    def update_source(self, sid, status, at): self.updates.append((sid, status))
    def ensure_act_artist(self, name): self.acts.append(name); return "act-" + name
    def find_event(self, aid, city, date): return next((e for e in self.existing + self.events if (e["artist_id"], e["city"], e["event_date"]) == (aid, city, date)), None)
    def jambase_event_source(self, url, aid): return "src-" + url[-1]
    def insert_event(self, row): self.events.append(row); return row


CATALOG = [{"artist_id": "a1", "artist_name": "Diljit Dosanjh"}]


def go(events, repo=None, monkey_dev=True, resps=None, **kw):
    import os
    os.environ["JAMBASE_PLAN"] = "developer" if monkey_dev else ""
    repo = repo or Repo()
    client = JamBaseClient("k", Session(*(resps or [Resp(200, {"events": events})])), sleep=lambda s: None)
    return repo, run_jambase(repo, client, CATALOG, now=NOW, **kw)


def test_event_becomes_unconfirmed_report_with_venue_city_and_link_as_returned():
    repo, stats = go([ev()])
    (row,) = repo.events
    assert (row["artist_id"], row["city"], row["event_date"], row["venue"]) == ("a1", "Mumbai", "2026-11-27", "Mahalaxmi Race Course")
    assert row["confidence"] == "unconfirmed" and row["booking_url"] == "https://tickets.example/x?a=1" and stats["jambase_new"] == 1


def test_trial_key_cannot_write_to_the_database():
    repo, stats = go([ev()], monkey_dev=False)
    assert repo.events == [] and stats["jambase_status"] == "refused_not_developer_plan"


def test_existing_event_is_never_modified_and_cancelled_is_not_created():
    existing = [{"artist_id": "a1", "city": "Mumbai", "event_date": "2026-11-27"}]
    repo, _ = go([ev(), ev(identifier="2", startDate="2026-12-01", eventStatus="https://schema.org/EventCancelled")], Repo(existing))
    assert repo.events == [] and repo.updates == [("s1", "ok")]


def test_unknown_city_is_rejected_not_guessed_and_festival_gets_an_act():
    fest = ev(identifier="3", name="Rolling Loud India", performer=[{"name": "Burna Boy"}, {"name": "Diljit Dosanjh"}],
              location={"name": "Loud Park", "address": {"addressLocality": {"name": "Hinjawadi"}}})
    repo, _ = go([fest])
    assert repo.events == []
    fest["location"]["address"]["addressLocality"] = {"name": "Goa"}
    repo, _ = go([fest])
    assert {e["artist_id"] for e in repo.events} == {"act-Rolling Loud India", "a1"}


def test_not_due_within_six_hours_and_rate_limit_is_recorded():
    repo, stats = go([ev()], Repo(last=(NOW - dt.timedelta(hours=1)).isoformat()))
    assert stats["jambase_status"] == "not_due" and repo.events == []
    repo, stats = go([], resps=[Resp(429)])
    assert stats["jambase_status"] == "rate_limited" and repo.updates == [("s1", "error")]


def test_parse_skips_online_and_missing_dates_and_source_url_is_india_scoped():
    assert parse_event({"name": "x"}) is None
    assert parse_event(ev(eventAttendanceMode="https://schema.org/OnlineEventAttendanceMode")) is None
    assert "geoCountryIso2=IN" in SOURCE_URL

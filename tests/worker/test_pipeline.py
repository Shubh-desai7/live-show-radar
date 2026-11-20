import datetime as dt

from worker.collectors.http import FetchResult, OK, ROBOTS_DISALLOWED
from worker.pipeline import run

NOW = dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.timezone.utc)
LATER = NOW + dt.timedelta(days=1)
PAGE = '<ul><li class="show">Sat 20 Dec 2026 Bengaluru <a href="/t">Tickets</a></li></ul>'


class FakeRepo:
    def __init__(self, artists, sources):
        self.artists, self.sources = artists, sources
        self.events, self.logs, self.updates, self.ensured, self.touched = [], [], [], [], []
        self.tickets = {}

    def tracked_artists(self): return self.artists
    def ensure_source(self, *a): self.ensured.append(a)
    def sources_to_check(self, types, ids, limit): return self.sources
    def last_content_ref(self, sid): return next((l[2] for l in reversed(self.logs) if l[0] == sid and l[3] == "processed"), None)
    def insert_log(self, sid, url, ref, status): self.logs.append((sid, url, ref, status))
    def find_event(self, aid, city, date):
        return next((e for e in self.events if (e["artist_id"], e["city"], e["event_date"]) == (aid, city, date)), None)
    def insert_event(self, row):
        ev = dict(row, event_id="e%d" % (len(self.events) + 1))
        self.events.append(ev)
        return ev
    def get_ticket(self, eid): return self.tickets.get(eid)
    def upsert_ticket(self, row): self.tickets[row["event_id"]] = dict(self.tickets.get(row["event_id"], {}), **row)
    def update_event(self, eid, values):
        next(e for e in self.events if e["event_id"] == eid).update(values)
    def touch_verified(self, sid, at): self.touched.append((sid, at))
    def update_source(self, sid, status, at): self.updates.append((sid, status))


class FakeFetcher:
    def __init__(self, result): self.result = result
    def fetch(self, url): return self.result


def page(text, url="https://band.example/tour"):
    return FakeFetcher(FetchResult(OK, url, text))


ARTIST = {"artist_id": "a1", "artist_name": "Band", "official_website": "https://band.example"}
RAGA = {"artist_id": "a2", "artist_name": "Raga", "official_website": None}
OWN = {"source_id": "s1", "source_type": "artist_website", "source_url": "https://band.example/tour", "artist_id": "a1"}
PROMO = {"source_id": "s2", "source_type": "promoter_website", "source_url": "https://promo.example/shows", "artist_id": None}


def test_event_from_artists_own_site_is_confirmed_with_source_and_timestamps():
    repo = FakeRepo([ARTIST], [OWN])
    changes = []
    stats = run(repo, page(PAGE), now=NOW, on_change=changes.append)
    ev = repo.events[0]
    assert stats["events_new"] == 1
    assert (ev["confidence"], ev["city"], ev["event_date"], ev["source_id"]) == ("confirmed", "Bengaluru", "2026-12-20", "s1")
    assert ev["booking_url"] == "https://band.example/t"
    assert ev["first_seen_at"] == ev["detected_at"] == ev["last_verified_at"] == NOW.isoformat()
    assert [c.kind for c in changes] == ["new_event"]


def test_unchanged_page_is_skipped_and_refreshes_last_verified():
    repo = FakeRepo([ARTIST], [OWN])
    run(repo, page(PAGE), now=NOW)
    stats = run(repo, page(PAGE), now=LATER)
    assert stats["unchanged"] == 1 and len(repo.events) == 1
    assert repo.touched == [("s1", LATER.isoformat())]


def test_changed_page_with_same_event_does_not_duplicate_but_reverifies():
    repo = FakeRepo([ARTIST], [OWN])
    run(repo, page(PAGE), now=NOW)
    stats = run(repo, page(PAGE + "<!-- changed -->"), now=LATER)
    assert stats["events_existing"] == 1 and len(repo.events) == 1
    assert repo.events[0]["last_verified_at"] == LATER.isoformat()


def test_ambiguous_artist_name_on_promoter_page_stays_rumoured_and_emits_nothing():
    repo = FakeRepo([RAGA], [PROMO])
    changes = []
    run(repo, page("<ul><li>Raga live concert 20 Dec 2026 Pune</li></ul>", PROMO["source_url"]), now=NOW, on_change=changes.append)
    assert [e["confidence"] for e in repo.events] == ["rumoured"] and changes == []


def test_unambiguous_artist_on_promoter_page_is_confirmed():
    nucleya = {"artist_id": "a3", "artist_name": "Nucleya", "official_website": None}
    repo = FakeRepo([nucleya], [PROMO])
    run(repo, page("<ul><li>Nucleya live 20 Dec 2026 Bengaluru</li><li>Other Act 21 Dec 2026 Mumbai</li></ul>", PROMO["source_url"]), now=NOW)
    assert [(e["city"], e["confidence"]) for e in repo.events] == [("Bengaluru", "confirmed")]


def test_official_source_upgrades_rumoured_event_and_takes_over_the_source():
    repo = FakeRepo([ARTIST], [OWN])
    repo.events.append({"event_id": "e0", "artist_id": "a1", "city": "Bengaluru", "event_date": "2026-12-20",
                        "confidence": "rumoured", "status": "scheduled", "source_id": "old", "booking_url": None})
    changes = []
    stats = run(repo, page(PAGE), now=NOW, on_change=changes.append)
    ev = repo.events[0]
    assert (ev["confidence"], ev["source_id"], ev["booking_url"]) == ("confirmed", "s1", "https://band.example/t")
    assert stats["events_upgraded"] == 1 and [c.kind for c in changes] == ["confirmed"]


def test_confirmed_event_is_never_downgraded_by_a_weaker_report():
    repo = FakeRepo([RAGA], [PROMO])
    repo.events.append({"event_id": "e0", "artist_id": "a2", "city": "Pune", "event_date": "2026-12-20",
                        "confidence": "confirmed", "status": "scheduled", "source_id": "x", "booking_url": None})
    run(repo, page("<ul><li>Raga live concert 20 Dec 2026 Pune</li></ul>", PROMO["source_url"]), now=NOW)
    assert repo.events[0]["confidence"] == "confirmed" and repo.events[0]["source_id"] == "x"


def test_official_cancellation_updates_status_and_notifies_once():
    repo = FakeRepo([ARTIST], [OWN])
    run(repo, page(PAGE), now=NOW)
    changes = []
    cancelled = '<ul><li class="show">Sat 20 Dec 2026 Bengaluru - CANCELLED</li></ul>'
    run(repo, page(cancelled), now=LATER, on_change=changes.append)
    assert repo.events[0]["status"] == "cancelled" and [c.kind for c in changes] == ["status_changed"]
    changes.clear()
    run(repo, page(cancelled + "<!-- x -->"), now=LATER, on_change=changes.append)
    assert changes == []                                    # already cancelled: no repeat alert


def test_cancellation_notice_for_untracked_show_is_ignored():
    repo = FakeRepo([ARTIST], [OWN])
    run(repo, page('<ul><li class="show">Sat 20 Dec 2026 Bengaluru - cancelled</li></ul>'), now=NOW)
    assert repo.events == []


def test_robots_blocked_source_is_recorded_and_nothing_saved():
    repo = FakeRepo([ARTIST], [OWN])
    stats = run(repo, FakeFetcher(FetchResult(ROBOTS_DISALLOWED, OWN["source_url"])), now=NOW)
    assert stats["failed"] == 1 and not repo.events and repo.updates == [("s1", "robots_disallowed")]


def test_dry_run_writes_nothing():
    repo = FakeRepo([ARTIST], [OWN])
    stats = run(repo, page(PAGE), now=NOW, dry_run=True)
    assert stats["events_new"] == 1 and not repo.events and not repo.logs and not repo.updates and not repo.ensured


def test_no_followed_artists_is_a_noop():
    assert run(FakeRepo([], []), FakeFetcher(None), now=NOW)["sources"] == 0


SALE = ('<ul><li class="show">Sat 20 Dec 2026 Bengaluru. Presale starts 5 Dec 2026 at 12 pm IST. '
        'General sale: 8 Dec 2026, 6 pm IST. Early bird tickets available. <a href="/t">Tickets</a></li></ul>')


def test_official_event_gets_ticket_row_marked_reliable():
    repo = FakeRepo([ARTIST], [OWN])
    stats = run(repo, page(SALE), now=NOW)
    t = repo.tickets["e1"]
    assert stats["tickets_saved"] == 1
    assert t["presale_opening"] == "2026-12-05T06:30:00+00:00"
    assert t["general_sale_opening"] == "2026-12-08T12:30:00+00:00"
    assert (t["early_bird_status"], t["timing_reliable"], t["booking_url"]) == ("available", True, "https://band.example/t")


def test_date_only_sale_is_stored_but_not_reliable():
    repo = FakeRepo([ARTIST], [OWN])
    run(repo, page('<ul><li class="show">Sat 20 Dec 2026 Bengaluru. Tickets on sale from 8 Dec 2026</li></ul>'), now=NOW)
    assert repo.tickets["e1"]["timing_reliable"] is False
    assert repo.tickets["e1"]["general_sale_opening"] is not None


def test_changed_sale_time_on_official_page_updates_the_ticket_and_unchanged_does_not_rewrite():
    repo = FakeRepo([ARTIST], [OWN])
    run(repo, page(SALE), now=NOW)
    stats = run(repo, page(SALE.replace("8 Dec 2026, 6 pm", "9 Dec 2026, 6 pm")), now=LATER)
    assert repo.tickets["e1"]["general_sale_opening"] == "2026-12-09T12:30:00+00:00"
    assert stats["tickets_saved"] == 1
    stats = run(repo, page(SALE.replace("8 Dec 2026, 6 pm", "9 Dec 2026, 6 pm") + "<!-- x -->"), now=LATER)
    assert stats["tickets_saved"] == 0


def test_rumoured_source_never_writes_tickets():
    raga = {"artist_id": "a2", "artist_name": "Raga", "official_website": None}
    repo = FakeRepo([raga], [PROMO])
    run(repo, page("<ul><li>Raga live concert 20 Dec 2026 Pune. General sale 8 Dec 2026 6 pm IST</li></ul>", PROMO["source_url"]), now=NOW)
    assert repo.tickets == {}


def test_wording_dropped_from_page_does_not_erase_known_dates():
    repo = FakeRepo([ARTIST], [OWN])
    run(repo, page(SALE), now=NOW)
    run(repo, page('<ul><li class="show">Sat 20 Dec 2026 Bengaluru. Tickets: see link</li></ul>'), now=LATER)
    assert repo.tickets["e1"]["general_sale_opening"] == "2026-12-08T12:30:00+00:00"

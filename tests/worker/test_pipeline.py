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

    def tracked_artist_ids(self): return [a["artist_id"] for a in self.artists]
    def catalog_artists(self, tracked_ids): return self.artists
    def source_urls(self): return {a[1] for a in self.ensured}
    def ensure_source(self, *a): self.ensured.append(a)
    def sources_to_check(self, types, tracked_ids, now_iso, t1, t2): return self.sources
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


import json as _json

LD_EVENT = {"@type": "MusicEvent", "name": "Band Live", "startDate": "2027-01-19T20:00:00+05:30",
            "location": {"name": "Palace Grounds", "address": {"addressLocality": "Bangalore"}},
            "performer": {"name": "Band"},
            "offers": {"url": "/tickets", "validFrom": "2026-12-08T18:00:00+05:30"}}


def ld_page(*events):
    return "".join('<script type="application/ld+json">%s</script>' % _json.dumps(e) for e in events)


def test_structured_event_saves_venue_name_and_exact_sale_time_as_reliable():
    repo = FakeRepo([ARTIST], [OWN])
    stats = run(repo, page(ld_page(LD_EVENT)), now=NOW)
    ev = repo.events[0]
    assert (ev["venue"], ev["event_name"], ev["city"], ev["confidence"]) == ("Palace Grounds", "Band Live", "Bengaluru", "confirmed")
    t = repo.tickets["e1"]
    assert t["general_sale_opening"] == "2026-12-08T12:30:00+00:00" and t["timing_reliable"] is True
    assert t["booking_url"] == "https://band.example/tickets" and stats["tickets_saved"] == 1


def test_past_shows_are_never_created_or_alerted():
    old = dict(LD_EVENT, startDate="2026-06-01T20:00:00+05:30")
    repo = FakeRepo([ARTIST], [OWN])
    changes = []
    stats = run(repo, page(ld_page(old)), now=NOW, on_change=changes.append)
    assert repo.events == [] and changes == [] and stats["past_skipped"] == 1


def test_promoter_structured_event_is_matched_to_the_followed_artist_by_performer():
    nucleya = {"artist_id": "a3", "artist_name": "Nucleya", "official_website": None}
    mine = dict(LD_EVENT, name="Bass Night", performer=[{"name": "Nucleya"}, {"name": "Someone Else"}])
    other = dict(LD_EVENT, name="Jazz Night", startDate="2027-01-20T20:00:00+05:30", performer={"name": "Other Act"})
    repo = FakeRepo([nucleya], [PROMO])
    run(repo, page(ld_page(mine, other), PROMO["source_url"]), now=NOW)
    assert [(e["artist_id"], e["event_name"]) for e in repo.events] == [("a3", "Bass Night")]


def test_official_site_fills_in_missing_venue_on_an_existing_event():
    repo = FakeRepo([ARTIST], [OWN])
    repo.events.append({"event_id": "e0", "artist_id": "a1", "city": "Bengaluru", "event_date": "2027-01-19",
                        "confidence": "confirmed", "status": "scheduled", "source_id": "s1", "booking_url": None,
                        "venue": None, "event_name": None})
    run(repo, page(ld_page(LD_EVENT)), now=NOW)
    ev = repo.events[0]
    assert (ev["venue"], ev["event_name"]) == ("Palace Grounds", "Band Live")


def test_changing_the_extractor_version_reprocesses_an_unchanged_page(monkeypatch):
    from worker import config
    repo = FakeRepo([ARTIST], [OWN])
    run(repo, page(PAGE), now=NOW)
    assert run(repo, page(PAGE), now=LATER)["unchanged"] == 1
    monkeypatch.setattr(config, "EXTRACTOR_VERSION", "next")
    stats = run(repo, page(PAGE), now=LATER)
    assert stats["unchanged"] == 0 and stats["events_existing"] == 1


def test_official_page_with_one_indian_ticket_link_fills_the_booking_url_of_an_existing_show():
    repo = FakeRepo([ARTIST], [OWN])
    repo.events.append({"event_id": "e0", "artist_id": "a1", "city": "Bengaluru", "event_date": "2026-12-20", "confidence": "confirmed",
                        "status": "scheduled", "source_id": "s1", "booking_url": None, "venue": None, "event_name": None})
    html = '<ul><li class="show">Sat 20 Dec 2026 Bengaluru</li></ul><a href="https://in.bookmyshow.com/events/band/ET9">Tour</a>'
    run(repo, page(html), now=NOW)
    assert repo.events[0]["booking_url"] == "https://in.bookmyshow.com/events/band/ET9"

import datetime as dt

from worker.extractors.dates import find_dates
from worker.extractors.roundup import act_name, city_from_line, extract_roundup
from worker.feeds_pipeline import run_feeds
from worker.collectors.http import FetchResult

TODAY = dt.date(2026, 11, 20)
HTML = """<p>Intro text</p>
<h2>Echoes of Earth</h2><p>Dec. 5 and 6, 2026</p><p>TBA, Bengaluru</p>
<p>Lineup includes Nucleya and more. <a href="https://www.district.in/events/eoe">Echoes of Earth details here</a></p>
<h2>Ziro Festival</h2><p>September 24 to 27, 2026</p><p>Ziro Valley, Arunachal Pradesh</p><p>old</p>
<h2>Hornbill Music Festival</h2><p>Dec. 1 to 10, 2026</p><p>Naga Heritage Village, Kisama</p>
<h2>Casa Bacardi</h2><p>Dec. 3 and 4, 2026</p><p>The Punarnava Resort, Dehradun</p>
<h2>DGTL India</h2><p>Nov. 13 and 14, 2026</p><p>Lalit Ashok, Bengaluru, Ballard Pier, Mumbai</p>
<h2>Two cities, future</h2><p>Dec. 20, 2026</p><p>Hall A, Pune and Hall B, Mumbai</p>
<h2>No date</h2><p>coming soon</p><p>Goa</p>
<h2>Locals District</h2><p>Dec. 18 to 20, 2026</p><p>Castle Mandawa, Rajasthan</p>"""


def test_date_ranges_with_to_and_ampersand_use_the_start_day():
    assert find_dates("Sept. 25 to 27, 2026") == [dt.date(2026, 9, 25)]
    assert find_dates("Oct. 3 and 4, 2026") == [dt.date(2026, 10, 3)]
    assert find_dates("Dec 5 & 6, 2026") == [dt.date(2026, 12, 5)]
    assert find_dates("Nov 20 and Dec 5, 2026") == [dt.date(2026, 12, 5)]     # different months are not a range


def test_roundup_events_any_indian_city_past_and_ambiguous_ones_dropped():
    evs = extract_roundup(HTML, "https://rs.example/guide", TODAY)
    got = {e.name: (e.event_date, e.city) for e in evs}
    assert got == {"Echoes of Earth": ("2026-12-05", "Bengaluru"), "Hornbill Music Festival": ("2026-12-01", "Kisama"),
                   "Casa Bacardi": ("2026-12-03", "Dehradun"), "Locals District": ("2026-12-18", "Castle Mandawa")}
    eoe = next(e for e in evs if e.name == "Echoes of Earth")
    assert eoe.venue is None and eoe.link == "https://www.district.in/events/eoe" and "Nucleya" in eoe.blurb


def test_links_back_to_the_publisher_itself_are_not_event_links():
    html = '<h2>X Fest</h2><p>Dec. 5, 2026</p><p>Hall, Pune <a href="https://rs.example/tag/x">more</a></p>'
    assert extract_roundup(html, "https://rs.example/guide", TODAY)[0].link is None


def test_city_and_act_name_helpers():
    assert city_from_line("Prism by Octavium, Bengaluru") == "Bengaluru"
    assert city_from_line("Mahalaxmi Racecourse, Mumbai") == "Mumbai"
    assert city_from_line("Panjim, Goa") == "Goa"
    assert city_from_line("Naga Heritage Village, Kisama") == "Kisama"
    assert city_from_line("Hall, Pune and Mumbai") is None
    assert city_from_line("TBA") is None
    assert act_name("Sunburn Festival 2026") == "Sunburn Festival" and act_name("MLBx: Mumbai 2026") == "MLBx: Mumbai"
    assert act_name("  Echoes   of Earth ") == "Echoes of Earth"


class Repo:
    def __init__(self): self.events, self.acts, self.sources, self.updates = [], {}, {}, []
    def source_urls(self): return set()
    def ensure_source(self, *a): pass
    def publisher_sources_due(self, now_iso, minutes): return [{"source_id": "f1", "source_url": "https://rs.example/feed"}]
    def update_source(self, sid, st, at): self.updates.append((sid, st))
    def ensure_act_artist(self, name): return self.acts.setdefault(name.lower(), "act%d" % (len(self.acts) + 1))
    def find_event(self, aid, city, date): return next((e for e in self.events if (e["artist_id"], e["city"], e["event_date"]) == (aid, city, date)), None)
    def article_source(self, url, aid): return "src"
    def insert_event(self, row): self.events.append(row); return row


class Fetcher:
    def __init__(self, text): self.text = text
    def fetch(self, url, **kw): return FetchResult("ok", url, self.text)


RSS = """<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>t</title><item><title>Festival guide</title>
<link>https://rs.example/guide</link><pubDate>Thu, 19 Nov 2026 10:00:00 GMT</pubDate>
<content:encoded><![CDATA[%s]]></content:encoded></item></channel></rss>""" % HTML


def test_roundups_create_an_unconfirmed_event_for_the_festival_and_for_lineup_artists_in_the_catalog():
    catalog = [{"artist_id": "nuc", "artist_name": "Nucleya"}]
    repo = Repo()
    stats = run_feeds(repo, Fetcher(RSS), catalog, now=dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc))
    by = {(e["artist_id"], e["event_name"]): e for e in repo.events}
    assert ("nuc", "Echoes of Earth") in by and ("act1", "Echoes of Earth") in by             # lineup artist AND the festival itself
    assert {e["confidence"] for e in repo.events} == {"unconfirmed"}
    assert by[("act1", "Echoes of Earth")]["booking_url"] == "https://www.district.in/events/eoe"
    assert stats["roundup_events_new"] == 5 and len(repo.events) == 5
    run_feeds(repo, Fetcher(RSS), catalog, now=dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc))
    assert len(repo.events) == 5                                                                # rerun never duplicates

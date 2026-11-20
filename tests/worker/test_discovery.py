import datetime as dt

import requests

from worker.collectors import http as httpmod
from worker.collectors.http import FetchResult
from worker.collectors.musicbrainz import AMBIGUOUS, ERROR, FOUND, NONE, MusicBrainzClient, SiteResult
from worker.discovery.sites import Discovery, discover_artist_site, discover_sites, page_mentions, tour_pages
from worker.extractors.links import unique_india_ticket_link
from worker.extractors.page import extract_all

NOW = dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.timezone.utc)


# ------------------------------------------------------------------ MusicBrainz client
class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._b, self.headers = status, body, headers or {}

    def json(self):
        if self._b is None:
            raise ValueError
        return self._b


class Session:
    def __init__(self, *responses):
        self.responses, self.headers, self.calls = list(responses), {}, []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def mb(*responses, sleeps=None):
    s = Session(*responses)
    return MusicBrainzClient(s, sleep=(sleeps.append if sleeps is not None else lambda x: None), clock=lambda: 0.0, min_interval=0), s


def search(*artists): return Resp(200, {"artists": list(artists)})
def lookup(*urls): return Resp(200, {"relations": [{"type": t, "url": {"resource": u}} for t, u in urls]})
ART = {"id": "mbid1", "name": "Prateek Kuhad", "score": 100}


def test_accepts_one_exact_high_score_match_and_its_official_homepage():
    c, s = mb(search(ART), lookup(("official homepage", "https://prateekkuhad.com/")))
    assert c.find_official_site("Prateek Kuhad") == SiteResult(FOUND, "https://prateekkuhad.com/")
    assert s.calls[0][1]["query"] == 'artist:"Prateek Kuhad"' and "User" not in s.headers.get("User-Agent", "")


def test_rejects_fuzzy_low_score_and_ambiguous_matches():
    assert mb(search({"id": "x", "name": "Viva La Coldplay", "score": 57}))[0].find_official_site("Coldplay").status == NONE
    assert mb(search({"id": "x", "name": "Coldplay Tribute", "score": 100}))[0].find_official_site("Coldplay").status == NONE
    two = [dict(ART), dict(ART, id="mbid2")]
    assert mb(search(*two))[0].find_official_site("Prateek Kuhad").status == AMBIGUOUS


def test_social_streaming_and_non_homepage_links_are_never_used():
    c, _ = mb(search(ART), lookup(("official homepage", "https://www.instagram.com/x"), ("official homepage", "https://linktr.ee/x"),
                                   ("social network", "https://example.com/")))
    assert c.find_official_site("Prateek Kuhad").status == NONE
    c, _ = mb(search(ART), lookup(("official homepage", "https://linktr.ee/x"), ("official homepage", "https://real.example/")))
    assert c.find_official_site("Prateek Kuhad").url == "https://real.example/"


def test_busy_server_is_retried_with_retry_after_then_gives_up_cleanly():
    sleeps = []
    c, s = mb(Resp(503, headers={"Retry-After": "2"}), search(ART), lookup(("official homepage", "https://a.example/")), sleeps=sleeps)
    assert c.find_official_site("Prateek Kuhad").status == FOUND and sleeps[0] >= 2
    c, _ = mb(*[Resp(503)] * 4)
    assert c.find_official_site("X").status == ERROR
    c, _ = mb(requests.ConnectionError("boom"))
    assert c.find_official_site("X").status == ERROR


def test_query_special_characters_are_escaped():
    c, s = mb(search())
    c.find_official_site('Say "Hi" \\ Band')
    assert s.calls[0][1]["query"] == 'artist:"Say \\"Hi\\" \\\\ Band"'


# ------------------------------------------------------------------ verification and tour-page finding
HOME = '<title>Prateek Kuhad | Official Website</title><a href="/tour">TOUR</a><a href="/events/">Events</a><a href="/shop">Shop</a><a href="https://other.example/tour">x</a><a href="/img.png">tour</a>'


def test_site_must_mention_the_artist_name():
    assert page_mentions(HOME, "Prateek Kuhad")
    assert not page_mentions("<title>Aditya Jagdhane</title><p>Welcome</p>", "Arijit Singh")
    assert not page_mentions("<p>Prateekkuhadfan</p>", "Prateek Kuhad")


def test_tour_pages_are_same_host_ranked_and_capped():
    assert tour_pages(HOME, "https://prateekkuhad.com/") == ["https://prateekkuhad.com/tour", "https://prateekkuhad.com/events/"]


def test_article_style_and_mention_only_links_are_not_tour_pages():
    html = ('<a href="/win-tickets-to-jonny-chris-london-show/">Win tickets</a><a href="/post-perfo/yiruma-live-in-america-2018/">Live in America</a>'
            '<a href="/news/tour-announced-today">Tour</a><a href="/tour?ref=x#top">Tour</a><a href="/a/b/c/tour">deep</a><a href="/live">Live</a>')
    assert tour_pages(html, "https://a.example/") == ["https://a.example/tour", "https://a.example/live"]


class FakeMB:
    def __init__(self, result): self.result = result
    def find_official_site(self, name): return self.result


class FakeFetcher:
    def __init__(self, result): self.result = result
    def fetch(self, url): return self.result


def test_discovery_outcomes():
    ok = FetchResult("ok", "https://www.prateekkuhad.com/", HOME)
    d = discover_artist_site("Prateek Kuhad", FakeMB(SiteResult(FOUND, "https://prateekkuhad.com/")), FakeFetcher(ok))
    assert d.status == "ok" and d.official_url == "https://www.prateekkuhad.com/"
    assert d.source_urls[0] == "https://www.prateekkuhad.com/" and len(d.source_urls) == 3
    wrong = FetchResult("ok", "https://adityajagdhane.in/", "<title>Aditya Jagdhane</title>")
    assert discover_artist_site("Arijit Singh", FakeMB(SiteResult(FOUND, "https://adityajagdhane.in/")), FakeFetcher(wrong)).status == "unverified"
    for fetched, expect in ((FetchResult("robots_disallowed", "u"), "blocked"), (FetchResult("blocked", "u"), "blocked"), (FetchResult("error", "u", detail="HTTP 500"), "error")):
        assert discover_artist_site("X", FakeMB(SiteResult(FOUND, "https://x.example/")), FakeFetcher(fetched)).status == expect
    assert discover_artist_site("X", FakeMB(SiteResult(NONE)), FakeFetcher(None)).status == "none"
    assert discover_artist_site("X", FakeMB(SiteResult(ERROR)), FakeFetcher(None)).status == "error"


def test_retry_windows_and_persistence():
    assert Discovery("ok").retry_days == 7 and Discovery("none").retry_days == 30 and Discovery("error").retry_days == 1

    class Repo:
        def __init__(self): self.saved = []
        def artists_needing_site(self, tracked, now_z, lt, lc): return [{"artist_id": "a1", "artist_name": "Prateek Kuhad", "metadata": {}}]
        def save_site_result(self, artist, d, now): self.saved.append((artist["artist_id"], d.status))
    repo = Repo()
    ok = FetchResult("ok", "https://www.prateekkuhad.com/", HOME)
    stats = discover_sites(repo, FakeMB(SiteResult(FOUND, "https://prateekkuhad.com/")), FakeFetcher(ok), ["a1"], NOW)
    assert repo.saved == [("a1", "ok")] and stats["sites_found"] == 1
    repo2 = Repo()
    discover_sites(repo2, FakeMB(SiteResult(FOUND, "https://prateekkuhad.com/")), FakeFetcher(ok), ["a1"], NOW, dry_run=True)
    assert repo2.saved == []                                         # dry run records nothing


# ------------------------------------------------------------------ official booking link fallback
ROWS = '<ul><li class="show">Sat 21 Nov 2026 Ahmedabad</li></ul>'


def test_unique_indian_ticketing_link_is_used_only_on_an_artists_own_site():
    html = ROWS + '<a href="https://in.bookmyshow.com/events/tour/ET1">Tour</a><a href="https://www.ticketmaster.com/x">Tickets</a>'
    assert unique_india_ticket_link(html, "https://a.example/") == "https://in.bookmyshow.com/events/tour/ET1"
    assert extract_all(html, "https://a.example/", official_owner=True)[0].booking_url == "https://in.bookmyshow.com/events/tour/ET1"
    assert extract_all(html, "https://a.example/", official_owner=False)[0].booking_url is None


def test_ambiguous_or_bare_homepage_ticket_links_are_not_used():
    two = '<a href="https://in.bookmyshow.com/events/a/ET1">a</a><a href="https://insider.in/event/b">b</a>'
    assert unique_india_ticket_link(two, "https://a.example/") is None
    assert unique_india_ticket_link('<a href="https://in.bookmyshow.com/">home</a>', "https://a.example/") is None
    same_twice = '<a href="https://in.bookmyshow.com/e/1">a</a><a href="https://in.bookmyshow.com/e/1#x">b</a>'
    assert unique_india_ticket_link(same_twice, "https://a.example/") == "https://in.bookmyshow.com/e/1"


def test_a_rows_own_link_wins_over_the_page_level_fallback():
    html = '<ul><li class="show">Sat 21 Nov 2026 Ahmedabad <a href="/book/amd">Book</a></li></ul><a href="https://in.bookmyshow.com/e/1">t</a>'
    assert extract_all(html, "https://a.example/", official_owner=True)[0].booking_url == "https://a.example/book/amd"

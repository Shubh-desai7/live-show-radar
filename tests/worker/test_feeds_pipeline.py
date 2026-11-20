import datetime as dt

from worker.collectors.http import FetchResult
from worker.collectors.publisher_feeds import PUBLISHER_FEEDS
from worker.feeds_pipeline import run_feeds
from worker.verification.classify import classify

NOW = dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc)
FEED = "https://news.example/feed"
RSS = """<rss version="2.0"><channel><title>t</title>
<item><title>Fred again.. to perform in Mumbai on December 9</title><link>https://news.example/a1</link><pubDate>Thu, 19 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Prism to perform live in Pune on Dec 12</title><link>https://news.example/a2</link><pubDate>Thu, 19 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Nucleya concert review: Delhi Dec 5</title><link>https://news.example/a3</link><pubDate>Thu, 19 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Weather update for Mumbai on Dec 9</title><link>https://news.example/a4</link><pubDate>Thu, 19 Nov 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""
CATALOG = [{"artist_id": "a1", "artist_name": "Fred again.."}, {"artist_id": "a2", "artist_name": "Prism"}, {"artist_id": "a3", "artist_name": "Nucleya"}]


class Repo:
    def __init__(self, existing=()):
        self.events, self.updates, self.ensured, self.sources = [], [], [], {}
        self.existing = list(existing)

    def source_urls(self): return {u for _, u, _ in self.ensured}
    def ensure_source(self, t, u, a): self.ensured.append((t, u, a))
    def publisher_sources_due(self, now_iso, minutes): return [{"source_id": "f1", "source_url": FEED}]
    def update_source(self, sid, status, at): self.updates.append((sid, status))
    def find_event(self, aid, city, date): return next((e for e in self.existing + self.events if (e["artist_id"], e["city"], e["event_date"]) == (aid, city, date)), None)
    def article_source(self, url, aid): self.sources[url] = aid; return "src-" + url[-2:]
    def insert_event(self, row): self.events.append(row); return row


class Fetcher:
    def __init__(self, result): self.result, self.urls = result, []
    def fetch(self, url, **kw):
        assert "respect_robots" not in kw, "feeds must honour robots.txt"
        self.urls.append(url)
        return self.result


def go(repo=None, result=None, **kw):
    repo = repo or Repo()
    stats = run_feeds(repo, Fetcher(result or FetchResult("ok", FEED, RSS)), CATALOG, now=NOW, **kw)
    return repo, stats


def test_reports_are_unconfirmed_linked_to_the_article_and_never_confirmed():
    repo, stats = go()
    by = {e["artist_id"]: e for e in repo.events}
    fred = by["a1"]
    assert (fred["city"], fred["event_date"], fred["confidence"]) == ("Mumbai", "2026-12-09", "unconfirmed")
    assert fred["source_id"] == "src-a1" and repo.sources == {"https://news.example/a1": "a1", "https://news.example/a2": "a2"}
    assert by["a2"]["confidence"] == "rumoured"                          # ambiguous name: capped lower
    assert "a3" not in by and len(repo.events) == 2 and stats["feed_reports_new"] == 2
    assert {e["confidence"] for e in repo.events} <= {"unconfirmed", "rumoured"}
    assert repo.updates == [("f1", "ok")]


def test_an_existing_event_is_never_overwritten_by_a_news_report():
    existing = [{"artist_id": "a1", "city": "Mumbai", "event_date": "2026-12-09", "confidence": "confirmed"}]
    repo, stats = go(Repo(existing))
    assert [e["artist_id"] for e in repo.events] == ["a2"] and stats["feed_reports_new"] == 1


def test_feed_sources_are_registered_and_a_failing_feed_is_recorded_not_fatal():
    repo, stats = go(result=FetchResult("robots_disallowed", FEED))
    assert {u for _, u, _ in repo.ensured} == set(PUBLISHER_FEEDS) and all(t == "publisher_rss" for t, _, _ in repo.ensured)
    assert repo.events == [] and repo.updates == [("f1", "robots_disallowed")] and stats["feeds_failed"] == 1


def test_dry_run_writes_nothing():
    repo, stats = go(dry_run=True)
    assert repo.events == [] and repo.updates == [] and repo.ensured == [] and stats["feed_reports_new"] == 2


def test_publisher_reports_can_only_ever_be_unconfirmed_or_rumoured():
    assert classify("publisher_rss", owner_source=False, ambiguous_name=False) == "unconfirmed"
    assert classify("publisher_rss", owner_source=True, ambiguous_name=False) == "unconfirmed"
    assert classify("publisher_rss", owner_source=False, ambiguous_name=True) == "rumoured"

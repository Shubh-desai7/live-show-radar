import datetime as dt

from worker.extractors.dates import find_dates_relative
from worker.extractors.feeds import FeedItem
from worker.extractors.news import candidate_from_item

PUB = dt.date(2026, 11, 20)
NOW = dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc)
ART = {"artist_id": "a1", "artist_name": "Fred again.."}


def item(title, summary="", days_ago=1):
    return FeedItem(title, "https://news.example/a", summary, NOW - dt.timedelta(days=days_ago))


def test_bare_day_month_is_read_as_the_next_occurrence_after_the_publication_date():
    assert find_dates_relative("Mumbai on Nov 27", PUB) == [dt.date(2026, 11, 27)]
    assert find_dates_relative("27th November", PUB) == [dt.date(2026, 11, 27)]
    assert find_dates_relative("Jan 9", PUB) == [dt.date(2027, 1, 9)]
    assert find_dates_relative("20-21 Dec", PUB) == [dt.date(2026, 12, 20)]


def test_explicit_years_win_and_far_or_past_inferences_are_rejected():
    assert find_dates_relative("Dec 20, 2026", PUB) == [dt.date(2026, 12, 20)]
    assert find_dates_relative("Nov 10", PUB) == []                 # next occurrence would be ~a year away: likely a past date
    assert find_dates_relative("Oct 3 show", PUB) == []
    assert find_dates_relative("nothing here", PUB) == []


def test_a_headline_with_artist_show_city_and_date_becomes_a_candidate():
    c = candidate_from_item(item("Fred again.. to perform in Mumbai on December 9 - Rolling Stone India"), ART, NOW)
    assert (c.city, c.event_date, c.ambiguous_name) == ("Mumbai", "2026-12-09", False)


def test_headlines_that_are_incomplete_ambiguous_old_or_not_about_a_show_are_skipped():
    for title in ("Fred again.. announces India tour: Delhi, Mumbai, Bengaluru",          # no date
                  "Fred again.. live in Mumbai or Pune on Dec 9",                           # two cities
                  "Fred again.. concert review: Mumbai Dec 9",                              # review
                  "Someone else to perform in Mumbai on December 9",                        # artist not named
                  "Fred again.. to perform in Mumbai on Dec 9 and Dec 12"):                 # two dates
        assert candidate_from_item(item(title), ART, NOW) is None, title
    assert candidate_from_item(item("Fred again.. to perform in Mumbai on Dec 9", days_ago=90), ART, NOW) is None
    future = FeedItem("Fred again.. to perform in Mumbai on Dec 9", "u", "", NOW + dt.timedelta(days=5))
    assert candidate_from_item(future, ART, NOW) is None


def test_ambiguous_artist_names_are_flagged_so_they_can_only_be_rumoured():
    prism = {"artist_id": "a2", "artist_name": "Prism"}
    c = candidate_from_item(item("Prism to perform live in Pune on Dec 12"), prism, NOW)
    assert c is not None and c.ambiguous_name


def test_html_entities_and_markup_in_feed_text_are_cleaned():
    c = candidate_from_item(item("Fred again.. &amp; friends: live in Mumbai on Dec 9", "<b>Tickets</b> on sale"), ART, NOW)
    assert c is not None and "&amp;" not in c.title and "<" not in c.title

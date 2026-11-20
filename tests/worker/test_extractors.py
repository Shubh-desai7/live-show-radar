import datetime as dt

from worker.extractors.cities import find_cities
from worker.extractors.dates import find_dates
from worker.extractors.feeds import parse_feed
from worker.extractors.html_events import extract_candidates
from worker.matching.artists import match_artists


def test_cities_normalise_aliases_and_dedupe():
    assert find_cities("Live in Bangalore, then Bombay and Bengaluru again") == ["Bengaluru", "Mumbai"]
    assert find_cities("Gurugram show") == ["Delhi NCR"]
    assert find_cities("nothing here") == []


def test_cities_need_word_boundaries():
    assert find_cities("Panjim, Pune") == ["Pune"]
    assert find_cities("Goatee festival") == []


def test_dates_require_explicit_year():
    assert find_dates("Dec 20 at the arena") == []
    assert find_dates("20th Dec 2026") == [dt.date(2026, 12, 20)]
    assert find_dates("December 20, 2026") == [dt.date(2026, 12, 20)]
    assert find_dates("on 2026-12-20") == [dt.date(2026, 12, 20)]


def test_date_ranges_use_start_day_and_invalid_dates_are_ignored():
    assert find_dates("20-21 Dec 2026") == [dt.date(2026, 12, 20)]
    assert find_dates("31 Feb 2026") == []


HTML = """
<html><body><nav>Home Bengaluru</nav>
<ul>
  <li class="show">Sat 20 Dec 2026 - Bengaluru - <a href="/tickets/blr">Buy tickets</a></li>
  <li class="show">Mumbai &amp; Pune, 1 Jan 2027</li>
  <li class="show">Coming soon to Hyderabad</li>
  <li class="show">Fri 9 Jan 2027, Chennai <a href="javascript:void(0)">info</a></li>
</ul></body></html>
"""


def test_html_candidates_need_one_city_and_one_date_per_block():
    cands = extract_candidates(HTML, "https://artist.example/tour")
    got = {(c.city, c.event_date): c.booking_url for c in cands}
    assert got == {
        ("Bengaluru", "2026-12-20"): "https://artist.example/tickets/blr",
        ("Chennai", "2027-01-09"): None,
    }


def test_feed_parsing_keeps_http_links_and_utc_dates():
    rss = """<rss version="2.0"><channel><title>t</title>
    <item><title>Band announces tour</title><link>https://news.example/a</link>
      <pubDate>Fri, 20 Nov 2026 10:00:00 GMT</pubDate><description>d</description></item>
    <item><title>bad</title><link>javascript:alert(1)</link></item></channel></rss>"""
    items = parse_feed(rss)
    assert len(items) == 1 and items[0].link == "https://news.example/a"
    assert items[0].published == dt.datetime(2026, 11, 20, 10, 0, tzinfo=dt.timezone.utc)


def test_artist_matching_is_whole_word_and_case_insensitive():
    artists = [{"artist_id": "1", "artist_name": "Nucleya"}, {"artist_id": "2", "artist_name": "Raga"}]
    assert [a["artist_id"] for a in match_artists("NUCLEYA live in Pune", artists)] == ["1"]
    assert match_artists("Ragas of India", artists) == []


def test_sale_dates_in_a_block_do_not_hide_or_replace_the_show_date():
    html = ('<ul><li class="show">Sat 20 Dec 2026 Bengaluru. Presale starts 5 Dec 2026 at 12 pm. '
            'General sale 8 Dec 2026, 6 pm.</li>'
            '<li class="show">Bengaluru. General sale 8 Dec 2026, 6 pm.</li></ul>')
    got = [(c.city, c.event_date) for c in extract_candidates(html, "https://a.example")]
    assert got == [("Bengaluru", "2026-12-20")]          # second block has no show date: no candidate

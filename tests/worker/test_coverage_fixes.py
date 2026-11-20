import json

from worker.extractors.cities import find_cities
from worker.extractors.dates import find_dates, has_ambiguous_numeric_date
from worker.extractors.html_events import extract_candidates
from worker.extractors.jsonld import extract_jsonld_events
from worker.matching.artists import match_artists_detailed
from worker.stats import Trace


def ld(name, loc):
    blk = {"@type": "MusicEvent", "name": name, "startDate": "2026-12-18T16:00:00+05:30", "location": loc}
    return '<script type="application/ld+json">%s</script>' % json.dumps(blk)


def test_jsonld_country_only_location_uses_city_in_title():
    (c,) = extract_jsonld_events(ld("Sunburn Arena ft. DJ Snake – Bangalore", {"@type": "Place", "name": "India"}), "https://x.example/")
    assert c.city == "Bengaluru"


def test_jsonld_country_only_and_no_city_in_title_is_rejected_with_reason():
    t = Trace()
    assert extract_jsonld_events(ld("Martin Garrix India Tour", {"@type": "Place", "name": "India"}), "https://x.example/", trace=t) == []
    assert t.counts().get("city_not_recognised") == 1


def test_numeric_dates_only_when_unambiguous():
    assert [d.isoformat() for d in find_dates("Show on 25/12/2026")] == ["2026-12-25"]
    assert find_dates("Show on 05/06/2026") == [] and has_ambiguous_numeric_date("Show on 05/06/2026")


def test_more_indian_cities_and_aliases():
    assert find_cities("Live in Nagpur") == ["Nagpur"]
    assert find_cities("Live in Vizag")


def test_html_block_without_year_is_traced_not_invented():
    t = Trace()
    html = "<ul><li>Live concert in Mumbai on 12 March, tickets on sale</li></ul>"
    assert extract_candidates(html, "https://x.example/", trace=t) == []
    assert t.counts().get("date_without_year") == 1


def test_matching_collapses_initials_and_aliases():
    a = [{"artist_id": "1", "artist_name": "A. R. Rahman"}]
    assert match_artists_detailed("AR Rahman live concert Chennai", a)
    assert match_artists_detailed("A.R. Rahman live in Pune", a)
    b = [{"artist_id": "2", "artist_name": "Divine", "metadata": {"aliases": ["Vivian Fernandes"]}}]
    assert match_artists_detailed("Vivian Fernandes live concert", b)


def test_leading_the_dropped_only_when_distinctive():
    assert match_artists_detailed("Weeknd live concert", [{"artist_id": "1", "artist_name": "The Weeknd"}])
    assert not match_artists_detailed("who live concert", [{"artist_id": "2", "artist_name": "The Who"}])

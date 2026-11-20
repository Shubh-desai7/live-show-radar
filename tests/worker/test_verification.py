import pytest

from worker.extractors.html_events import detect_status
from worker.matching.artists import is_ambiguous_name, match_artists_detailed, normalize
from worker.verification.classify import classify, is_upgrade


@pytest.mark.parametrize("stype,owner,amb,expected", [
    ("artist_website", True, False, "confirmed"),
    ("artist_website", False, False, "rumoured"),      # not the artist's own site
    ("promoter_website", False, False, "confirmed"),
    ("promoter_website", False, True, "rumoured"),
    ("newsletter", False, False, "unconfirmed"),
    ("google_news_rss", False, False, "unconfirmed"),
    ("newsletter", False, True, "rumoured"),
    ("mystery", True, False, "rumoured"),
])
def test_classification_rules(stype, owner, amb, expected):
    assert classify(stype, owner_source=owner, ambiguous_name=amb) == expected


def test_only_upward_moves_count_as_upgrades():
    assert is_upgrade("rumoured", "unconfirmed") and is_upgrade("unconfirmed", "confirmed")
    assert not is_upgrade("confirmed", "unconfirmed") and not is_upgrade("confirmed", "confirmed")


def test_normalisation_handles_accents_ampersand_and_punctuation():
    assert normalize("  Sigur  Rós ") == "sigur ros"
    assert normalize("Ritviz & Co.") == normalize("Ritviz and Co")


def test_ambiguity_flags_short_or_common_single_words_only():
    assert is_ambiguous_name("Raga") and is_ambiguous_name("Prism") and is_ambiguous_name("Zed")
    assert not is_ambiguous_name("Prateek Kuhad") and not is_ambiguous_name("Nucleya")


def test_ambiguous_names_need_concert_context():
    a = [{"artist_id": "1", "artist_name": "Prism"}]
    assert match_artists_detailed("A prism of colours in Pune", a) == []
    hit = match_artists_detailed("Prism live in Pune", a)
    assert len(hit) == 1 and hit[0].ambiguous


def test_accent_insensitive_match():
    a = [{"artist_id": "1", "artist_name": "Sigur Rós"}]
    assert len(match_artists_detailed("sigur ros tour dates", a)) == 1


@pytest.mark.parametrize("text,expected", [
    ("Show cancelled due to rain", "cancelled"), ("CANCELED", "cancelled"),
    ("Postponed to a later date", "postponed"), ("Rescheduled", "postponed"),
    ("Tickets on sale now", "scheduled"),
])
def test_status_detection(text, expected):
    assert detect_status(text) == expected

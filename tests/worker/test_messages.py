import datetime as dt

import pytest

from worker.notifications.messages import FOOTER, fmt_event_date, fmt_moment, fmt_remaining, render

NOW = dt.datetime(2026, 12, 1, 6, 30, tzinfo=dt.timezone.utc)
EV = {"artist_name": "Nucleya", "city": "Bengaluru", "event_date": "2027-01-19", "status": "scheduled", "booking_url": "https://x.example/book"}
TICKET = {"presale_opening": "2026-12-01T08:30:00+00:00", "general_sale_opening": "2026-12-03T12:30:00+00:00",
          "presale_registration_deadline": None, "booking_url": None, "timing_reliable": True}


def test_times_render_in_the_users_timezone_with_zone_abbreviation():
    assert fmt_moment("2026-12-01T08:30:00+00:00", "Asia/Kolkata") == "1 Dec 2026, 2:00 PM IST"
    assert fmt_moment("2026-12-01T08:30:00Z", "UTC") == "1 Dec 2026, 8:30 AM UTC"
    assert fmt_moment("2026-12-01T08:30:00Z", "Not/AZone").endswith("IST")      # bad zone falls back to IST


def test_remaining_time_wording():
    assert fmt_remaining("2026-12-01T08:30:00+00:00", NOW) == "in about 2 hours"
    assert fmt_remaining("2026-12-01T06:50:00+00:00", NOW) == "in about 20 minutes"
    assert fmt_remaining("2026-12-02T06:30:00+00:00", NOW) == "in about 24 hours"
    assert fmt_remaining("2026-12-08T06:30:00+00:00", NOW) == "in about 7 days"


def test_reminder_message_has_headline_exact_time_link_and_disclaimer():
    text = render("presale_opening", EV, TICKET, "Asia/Kolkata", NOW)
    assert text.splitlines()[0] == "Presale opens in about 2 hours"
    assert "Nucleya: Bengaluru, Tue 19 Jan 2027" in text and "Presale opens: 1 Dec 2026, 2:00 PM IST" in text
    assert "https://x.example/book" in text and text.endswith(FOOTER)


def test_new_event_lists_only_reliable_ticket_times():
    assert "General sale opens: 3 Dec 2026, 6:00 PM IST" in render("new_event", EV, TICKET, "Asia/Kolkata", NOW)
    assert "General sale" not in render("new_event", EV, dict(TICKET, timing_reliable=False), "Asia/Kolkata", NOW)


def test_cancel_and_update_messages():
    assert render("event_cancelled", EV, None, "UTC", NOW).startswith("Show cancelled")
    assert render("event_update", dict(EV, status="postponed"), None, "UTC", NOW).startswith("Show postponed")


def test_missing_city_and_date_are_never_invented():
    text = render("event_cancelled", {"artist_name": "X", "city": None, "event_date": None}, None, "UTC", NOW)
    assert "city to be announced" in text and "date to be announced" in text
    assert fmt_event_date(None) == "date to be announced"


def test_unknown_type_is_an_error():
    with pytest.raises(ValueError):
        render("nope", EV, None, "UTC", NOW)

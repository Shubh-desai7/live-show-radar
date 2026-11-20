import datetime as dt

from worker.extractors.tickets import (
    GENERAL_SALE, IST, PRESALE_OPENING, PRESALE_REGISTRATION, extract_ticket_info,
)


def utc(y, mo, d, h=0, mi=0, tz=IST):
    return dt.datetime(y, mo, d, h, mi, tzinfo=tz).astimezone(dt.timezone.utc)


def test_full_set_with_times_is_reliable():
    t = extract_ticket_info(
        "Presale registration closes 1 Dec 2026, 11:59 pm IST. Presale starts 5 Dec 2026 at 12 pm. "
        "General sale: 8 Dec 2026, 6:00 pm IST. Early bird tickets available!", "2027-01-20")
    assert t.moments[PRESALE_REGISTRATION].at == utc(2026, 12, 1, 23, 59)
    assert t.moments[PRESALE_OPENING].at == utc(2026, 12, 5, 12, 0)
    assert t.moments[GENERAL_SALE].at == utc(2026, 12, 8, 18, 0)
    assert t.reliable and t.early_bird_status == "available"


def test_registration_opens_is_not_a_deadline_and_does_not_leak_into_presale():
    t = extract_ticket_info("Presale registration opens 1 Dec 2026. Presale starts 5 Dec 2026 6 pm", "2027-01-20")
    assert PRESALE_REGISTRATION not in t.moments
    assert t.moments[PRESALE_OPENING].at == utc(2026, 12, 5, 18, 0)


def test_date_only_moment_is_stored_but_not_reliable():
    t = extract_ticket_info("Tickets on sale from 8 Dec 2026", "2027-01-20")
    assert t.moments[GENERAL_SALE].at == utc(2026, 12, 8, 0, 0) and not t.reliable


def test_missing_year_means_no_moment():
    t = extract_ticket_info("Presale starts 5 Dec at 6 pm. General sale 8 Dec", "2027-01-20")
    assert t.moments == {} and t.is_empty()


def test_unknown_timezone_makes_moment_imprecise_but_utc_and_offsets_are_understood():
    assert not extract_ticket_info("General sale 8 Dec 2026 6 pm EST", "2027-01-20").reliable
    assert extract_ticket_info("General sale 8 Dec 2026 12:30 UTC", "2027-01-20").moments[GENERAL_SALE].at == utc(2026, 12, 8, 12, 30, dt.timezone.utc)
    assert extract_ticket_info("General sale 8 Dec 2026 6 pm GMT+5:30", "2027-01-20").moments[GENERAL_SALE].at == utc(2026, 12, 8, 18, 0)
    assert extract_ticket_info("General sale 8 Dec 2026 18:00 +0530", "2027-01-20").moments[GENERAL_SALE].at == utc(2026, 12, 8, 18, 0)


def test_mixed_precision_is_not_reliable():
    t = extract_ticket_info("Presale starts 5 Dec 2026 6 pm. General sale 8 Dec 2026", "2027-01-20")
    assert len(t.moments) == 2 and not t.reliable


def test_sale_on_or_after_show_day_is_discarded():
    t = extract_ticket_info("Sat 20 Dec 2026 Bengaluru. Tickets on sale 20 Dec 2026 6 pm", "2026-12-20")
    assert t.moments == {}


def test_early_bird_states():
    assert extract_ticket_info("Early bird tickets sold out").early_bird_status == "ended"
    assert extract_ticket_info("No early bird offer for this show").early_bird_status == "not_offered"
    assert extract_ticket_info("Early bird pricing mentioned").early_bird_status == "unknown"
    assert extract_ticket_info("Nothing about tickets").is_empty()


def test_first_value_per_kind_wins():
    t = extract_ticket_info("General sale 8 Dec 2026 6 pm. Also general sale 9 Dec 2026 6 pm", "2027-01-20")
    assert t.moments[GENERAL_SALE].at == utc(2026, 12, 8, 18, 0)

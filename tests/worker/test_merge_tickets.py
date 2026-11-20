import datetime as dt

from worker.extractors.tickets import GENERAL_SALE, IST, Moment, TicketInfo
from worker.verification.tickets import merge_tickets

STAMP = "2026-11-20T12:00:00+00:00"


def info(day=8, precise=True, early="unknown"):
    at = dt.datetime(2026, 12, day, 18, 0, tzinfo=IST).astimezone(dt.timezone.utc)
    return TicketInfo({GENERAL_SALE: Moment(at, precise)}, early)


def test_new_row_requires_some_information():
    assert merge_tickets(None, TicketInfo(), None, True, STAMP) is None
    assert merge_tickets(None, info(), None, True, STAMP)["timing_reliable"] is True


def test_unofficial_source_can_never_mark_timing_reliable():
    assert merge_tickets(None, info(), None, False, STAMP)["timing_reliable"] is False


def test_identical_data_is_a_no_op_even_with_different_timestamp_formats():
    existing = {"general_sale_opening": "2026-12-08T12:30:00Z", "presale_opening": None,
                "presale_registration_deadline": None, "early_bird_status": "unknown",
                "booking_url": None, "timing_reliable": True}
    assert merge_tickets(existing, info(), None, True, STAMP) is None


def test_unknown_early_bird_keeps_known_status_and_new_date_replaces_old():
    existing = {"general_sale_opening": "2026-12-08T12:30:00+00:00", "early_bird_status": "ended",
                "booking_url": "https://x.example", "timing_reliable": True}
    row = merge_tickets(existing, info(day=9), None, True, STAMP)
    assert row["early_bird_status"] == "ended" and row["booking_url"] == "https://x.example"
    assert row["general_sale_opening"].startswith("2026-12-09")


def test_precision_loss_flips_reliability_off():
    existing = {"general_sale_opening": "2026-12-08T12:30:00+00:00", "timing_reliable": True}
    assert merge_tickets(existing, info(day=9, precise=False), None, True, STAMP)["timing_reliable"] is False

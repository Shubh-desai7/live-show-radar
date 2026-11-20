import datetime as dt
import json

from worker.extractors.jsonld import extract_jsonld_events
from worker.extractors.page import extract_all
from worker.extractors.tickets import GENERAL_SALE, IST, PRESALE_OPENING

BASE = "https://band.example/tour"


def page(*blocks, extra=""):
    return "<html><head>%s</head><body>%s</body></html>" % (
        "".join('<script type="application/ld+json">%s</script>' % (b if isinstance(b, str) else json.dumps(b).replace("</", "<\\/")) for b in blocks), extra)


def event(**kw):
    e = {"@type": "MusicEvent", "name": "Nucleya Live", "startDate": "2027-02-01T20:00:00+05:30",
         "location": {"@type": "Place", "name": "Palace Grounds", "address": {"addressLocality": "Bangalore"}},
         "performer": {"@type": "Person", "name": "Nucleya"},
         "offers": {"@type": "Offer", "url": "/tickets/blr", "validFrom": "2026-12-08T18:00:00+05:30"}}
    e.update(kw)
    return e


def test_full_event_gives_exact_venue_name_city_date_link_and_sale_time():
    (c,) = extract_jsonld_events(page(event()), BASE)
    assert (c.city, c.event_date, c.venue, c.event_name) == ("Bengaluru", "2027-02-01", "Palace Grounds", "Nucleya Live")
    assert c.performers == ["Nucleya"] and c.booking_url == "https://band.example/tickets/blr" and c.status == "scheduled"
    m = c.tickets.moments[GENERAL_SALE]
    assert m.precise and m.at == dt.datetime(2026, 12, 8, 18, 0, tzinfo=IST).astimezone(dt.timezone.utc)
    assert c.tickets.reliable


def test_handles_graph_arrays_and_item_lists():
    graph = {"@graph": [{"@type": "WebSite"}, event(name="A", startDate="2027-02-01")]}
    lst = [event(name="B", startDate="2027-02-02")]
    itemlist = {"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "item": event(name="C", startDate="2027-02-03")}]}
    names = {c.event_name for c in extract_jsonld_events(page(graph, lst, itemlist), BASE)}
    assert names == {"A", "B", "C"}


def test_status_and_online_events():
    cancelled = event(eventStatus="https://schema.org/EventCancelled")
    postponed = event(name="P", startDate="2027-03-01", eventStatus="EventRescheduled")
    online = event(name="O", startDate="2027-04-01", eventAttendanceMode="https://schema.org/OnlineEventAttendanceMode")
    got = {c.event_name: c.status for c in extract_jsonld_events(page(cancelled, postponed, online), BASE)}
    assert got == {"Nucleya Live": "cancelled", "P": "postponed"}


def test_unknown_or_ambiguous_city_or_bad_date_are_skipped_not_guessed():
    far = event(location={"name": "Wembley", "address": {"addressLocality": "London"}})
    two = event(location={"name": "Hall", "address": "Mumbai or Pune"})
    nodate = event(startDate="soon")
    badday = event(startDate="2027-02-31")
    assert extract_jsonld_events(page(far, two, nodate, badday), BASE) == []


def test_address_as_plain_string_and_venue_name_fallback_for_city():
    c = extract_jsonld_events(page(event(location="Jio World Garden, Mumbai")), BASE)
    assert [x.city for x in c] == ["Mumbai"] and c[0].venue is None


def test_sale_time_precision_and_presale_and_early_bird_offers():
    date_only = event(offers={"@type": "Offer", "validFrom": "2026-12-08"})
    no_zone = event(name="Z", startDate="2027-02-05", offers={"validFrom": "2026-12-08T18:00:00"})
    presale = event(name="Pre", startDate="2027-02-06", offers=[
        {"name": "Presale for members", "validFrom": "2026-12-01T12:00:00+05:30"},
        {"name": "General", "validFrom": "2026-12-03T12:00:00+05:30"},
        {"name": "Early Bird", "validFrom": "2026-11-25T12:00:00+05:30"}])
    got = {c.event_name: c.tickets for c in extract_jsonld_events(page(date_only, no_zone, presale), BASE)}
    assert not got["Nucleya Live"].reliable                          # date only
    assert got["Z"].moments[GENERAL_SALE].precise is False           # time but no zone: not precise
    assert set(got["Pre"].moments) == {PRESALE_OPENING, GENERAL_SALE}
    assert got["Pre"].early_bird_status == "available" and got["Pre"].reliable


def test_hostile_and_malformed_input_is_contained():
    evil = event(name="<script>alert(1)</script>\x00\x07 Show\n\nnow", offers={"url": "javascript:alert(1)"},
                 location={"name": "Hall" + "x" * 500, "address": {"addressLocality": "Pune"}})
    html = page("{not json", "<!-- {\"@type\":\"Event\"} -->", evil, extra="<script type='application/ld+json'></script>")
    (c,) = extract_jsonld_events(html, BASE)
    assert "\x00" not in c.event_name and "\n" not in c.event_name and len(c.venue) <= 200
    assert c.booking_url is None                                     # non-http(s) URL dropped
    # the string is stored as inert text; rendering escapes it (React) and Telegram messages are plain text


def test_cap_and_dedupe():
    many = [event(name="n%d" % i, startDate="2027-02-01") for i in range(3)] + [event(name="n0")]
    assert len(extract_jsonld_events(page(many), BASE)) == 3


def test_extract_all_prefers_structured_and_keeps_text_only_shows():
    html = page(event(offers=None), extra='<ul><li class="show">Sat 1 Feb 2027 Bengaluru <a href="/book">Book now</a></li>'
                                          '<li class="show">Sun 2 Feb 2027 Mumbai</li></ul>')
    got = {(c.city, c.event_date): c for c in extract_all(html, BASE)}
    assert set(got) == {("Bengaluru", "2027-02-01"), ("Mumbai", "2027-02-02")}
    assert got[("Bengaluru", "2027-02-01")].venue == "Palace Grounds"              # structured record wins
    assert got[("Bengaluru", "2027-02-01")].booking_url == "https://band.example/book"   # filled from the text block


def test_html_entities_are_decoded_and_placeholder_performers_ignored():
    e = event(name="Anyma Presents Aeden &#8211; Mumbai &amp; Co", performer="Organization",
              location={"name": "Mahalaxmi Race Course, Mumbai", "address": ""})
    (c,) = extract_jsonld_events(page(e), BASE)
    assert c.event_name == "Anyma Presents Aeden – Mumbai & Co" and c.performers == []
    assert c.city == "Mumbai"                                       # city found from the venue name
    assert "Organization" not in c.snippet


def test_real_names_in_a_performer_list_survive_next_to_placeholders():
    e = event(performer=[{"@type": "Organization", "name": "Organization"}, {"@type": "Person", "name": "Nucleya"}, "TBA"])
    assert extract_jsonld_events(page(e), BASE)[0].performers == ["Nucleya"]

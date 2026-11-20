"""All extractors for one page: structured JSON-LD events first, then text-derived blocks for what remains."""
from __future__ import annotations

from typing import List

from worker.extractors.html_events import Candidate, extract_candidates
from worker.extractors.jsonld import extract_jsonld_events
from worker.extractors.links import unique_india_ticket_link


def extract_all(html: str, base_url: str, official_owner: bool = False) -> List[Candidate]:
    structured = extract_jsonld_events(html, base_url)
    merged = list(structured)
    by_key = {(c.city, c.event_date): c for c in structured}
    for c in extract_candidates(html, base_url):
        existing = by_key.get((c.city, c.event_date))
        if existing is None:
            merged.append(c)
        elif not existing.booking_url and c.booking_url:
            existing.booking_url = c.booking_url           # same show seen both ways: keep the richer record
    if official_owner:                                   # an artist's own page: use its one Indian ticketing link if unambiguous
        fallback = unique_india_ticket_link(html, base_url)
        if fallback:
            for c in merged:
                if not c.booking_url:
                    c.booking_url = fallback
    return merged

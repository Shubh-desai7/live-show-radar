"""All extractors for one page: structured JSON-LD events first, then text-derived blocks for what remains."""
from __future__ import annotations

from typing import List

from worker.extractors.html_events import Candidate, extract_candidates
from worker.extractors.jsonld import extract_jsonld_events


def extract_all(html: str, base_url: str) -> List[Candidate]:
    structured = extract_jsonld_events(html, base_url)
    merged = list(structured)
    by_key = {(c.city, c.event_date): c for c in structured}
    for c in extract_candidates(html, base_url):
        existing = by_key.get((c.city, c.event_date))
        if existing is None:
            merged.append(c)
        elif not existing.booking_url and c.booking_url:
            existing.booking_url = c.booking_url           # same show seen both ways: keep the richer record
    return merged

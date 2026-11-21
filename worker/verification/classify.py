"""Event confidence rules (see CLAUDE.md "Verification states").

confirmed   : reported by an official source: the artist's own website, or a promoter's website
              that names the artist unambiguously.
unconfirmed : reported only by a credible secondary source (newsletter / publisher feed).
rumoured    : anything weaker, including promoter-page matches on an ambiguous artist name.
              Internal only: never shown to users.
Confidence only ever moves up automatically. A confirmed event is never downgraded.
"""
from __future__ import annotations

CONFIRMED, UNCONFIRMED, RUMOURED = "confirmed", "unconfirmed", "rumoured"
RANK = {RUMOURED: 0, UNCONFIRMED: 1, CONFIRMED: 2}

OFFICIAL_TYPES = ("artist_website", "promoter_website")
SECONDARY_TYPES = ("newsletter", "google_news_rss", "publisher_rss", "jambase")


def classify(source_type: str, *, owner_source: bool, ambiguous_name: bool) -> str:
    """owner_source: the source belongs to the event's own artist (their official site)."""
    if source_type == "artist_website" and owner_source:
        return CONFIRMED
    if source_type == "promoter_website":
        return RUMOURED if ambiguous_name else CONFIRMED
    if source_type in SECONDARY_TYPES:
        return RUMOURED if ambiguous_name else UNCONFIRMED
    return RUMOURED


def is_upgrade(old: str, new: str) -> bool:
    return RANK[new] > RANK[old]


def is_official(confidence: str) -> bool:
    return confidence == CONFIRMED

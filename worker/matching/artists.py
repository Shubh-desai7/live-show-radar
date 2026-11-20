"""Match tracked artists in free text.

Names are normalised (case, accents, '&' vs 'and', punctuation, spacing) and matched on whole-word
boundaries. A short or common single-word name ("Raga", "Prism") is *ambiguous*: it only matches
when the text also has concert context, and the match is flagged so it can never be confirmed.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List

CONTEXT = re.compile(r"\b(live|concert|tour|gig|perform\w*|headlin\w*|presents?|show|festival|tickets?)\b", re.IGNORECASE)

# Single words that are also ordinary words / very common names. Extend as real data shows problems.
COMMON_WORDS = {
    "queen", "prism", "blue", "love", "home", "indus", "raga", "rock", "pop", "soul", "gold", "echo",
    "river", "storm", "fire", "light", "dream", "dreams", "wild", "alone", "night", "moon", "sun",
    "ghost", "tool", "muse", "kiss", "future", "passenger", "sting", "eagles", "twice", "seventeen", "disturbed",
    "bastille", "keane", "tame", "oasis", "cactus", "euphoria", "advaita", "silk", "soulmate", "sanam", "agam",
}
# Multi-word names that are also ordinary phrases: treated as ambiguous too.
AMBIGUOUS_PHRASES = {"take that", "the script", "silk route", "red velvet", "indian ocean", "the local train", "fall out boy"}


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.casefold().replace("&", " and ")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def is_ambiguous_name(name: str) -> bool:
    n = normalize(name)
    if n in AMBIGUOUS_PHRASES:
        return True
    tokens = n.split()
    if len(tokens) != 1:
        return False
    return len(tokens[0]) <= 4 or tokens[0] in COMMON_WORDS


@dataclass
class Match:
    artist: Dict[str, str]
    ambiguous: bool


def match_artists_detailed(text: str, artists: List[Dict[str, str]]) -> List[Match]:
    haystack = " " + normalize(text) + " "
    has_context = bool(CONTEXT.search(text))
    hits: List[Match] = []
    for a in artists:
        needle = normalize(a["artist_name"])
        if len(needle) < 3:
            continue
        if (" " + needle + " ") not in haystack:
            continue
        ambiguous = is_ambiguous_name(a["artist_name"])
        if ambiguous and not has_context:
            continue
        hits.append(Match(a, ambiguous))
    return hits


def match_artists(text: str, artists: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [m.artist for m in match_artists_detailed(text, artists)]

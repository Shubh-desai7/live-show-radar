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


def collapse_initials(norm: str) -> str:
    """'a r rahman' -> 'ar rahman' so 'A. R. Rahman', 'A.R. Rahman' and 'AR Rahman' are one name."""
    out: List[str] = []
    run = ""
    for tok in norm.split():
        if len(tok) == 1 and tok.isalpha():
            run += tok
            continue
        if run:
            out.append(run)
            run = ""
        out.append(tok)
    if run:
        out.append(run)
    return " ".join(out)


def name_variants(artist: Dict) -> List[str]:
    """Normalised spellings to look for: the name, initials collapsed, a dropped leading 'The' (only when what is
    left is distinctive) and any explicit aliases stored in artists.metadata.aliases."""
    names = [artist["artist_name"]]
    meta = artist.get("metadata")
    if isinstance(meta, dict) and isinstance(meta.get("aliases"), list):
        names += [a for a in meta["aliases"] if isinstance(a, str)]
    variants: List[str] = []
    for n in names:
        norm = normalize(n)
        for v in (norm, collapse_initials(norm)):
            if v and v not in variants:
                variants.append(v)
        toks = norm.split()
        if len(toks) == 2 and toks[0] == "the" and len(toks[1]) >= 5 and toks[1] not in COMMON_WORDS:
            if toks[1] not in variants:
                variants.append(toks[1])
    return variants


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
    norm_text = normalize(text)
    haystack = " " + norm_text + " " + collapse_initials(norm_text) + " "
    has_context = bool(CONTEXT.search(text))
    hits: List[Match] = []
    for a in artists:
        if not any(len(v) >= 3 and (" " + v + " ") in haystack for v in name_variants(a)):
            continue
        ambiguous = is_ambiguous_name(a["artist_name"])
        if ambiguous and not has_context:
            continue
        hits.append(Match(a, ambiguous))
    return hits


def match_artists(text: str, artists: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [m.artist for m in match_artists_detailed(text, artists)]

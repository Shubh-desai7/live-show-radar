"""City detection. Canonical names match lib/cities.ts in the web app."""
from __future__ import annotations

import re
from typing import List

# alias (lowercase) -> canonical city
ALIASES = {
    "bengaluru": "Bengaluru", "bangalore": "Bengaluru",
    "mumbai": "Mumbai", "bombay": "Mumbai",
    "delhi": "Delhi NCR", "new delhi": "Delhi NCR", "delhi ncr": "Delhi NCR", "ncr": "Delhi NCR",
    "gurgaon": "Delhi NCR", "gurugram": "Delhi NCR", "noida": "Delhi NCR",
    "hyderabad": "Hyderabad",
    "chennai": "Chennai", "madras": "Chennai",
    "kolkata": "Kolkata", "calcutta": "Kolkata",
    "pune": "Pune", "ahmedabad": "Ahmedabad", "goa": "Goa", "jaipur": "Jaipur",
    "chandigarh": "Chandigarh",
    "kochi": "Kochi", "cochin": "Kochi",
    "lucknow": "Lucknow", "indore": "Indore", "guwahati": "Guwahati", "shillong": "Shillong",
}

_PATTERN = re.compile(
    r"\b(" + "|".join(sorted((re.escape(a) for a in ALIASES), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def find_cities(text: str) -> List[str]:
    """Canonical cities mentioned in text, in order of first appearance, without duplicates."""
    seen: List[str] = []
    for m in _PATTERN.finditer(text):
        city = ALIASES[m.group(1).lower()]
        if city not in seen:
            seen.append(city)
    return seen

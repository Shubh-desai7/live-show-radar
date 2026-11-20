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
    # Beyond the 16 selectable cities: shown on /shows, never used for alerts. Added so shows there are not silently lost.
    "nagpur": "Nagpur", "surat": "Surat", "vadodara": "Vadodara", "baroda": "Vadodara", "rajkot": "Rajkot", "bhopal": "Bhopal",
    "bhubaneswar": "Bhubaneswar", "visakhapatnam": "Visakhapatnam", "vizag": "Visakhapatnam", "vijayawada": "Vijayawada",
    "coimbatore": "Coimbatore", "madurai": "Madurai", "thiruvananthapuram": "Thiruvananthapuram", "trivandrum": "Thiruvananthapuram",
    "kozhikode": "Kozhikode", "calicut": "Kozhikode", "mysuru": "Mysuru", "mysore": "Mysuru", "mangaluru": "Mangaluru",
    "mangalore": "Mangaluru", "dehradun": "Dehradun", "amritsar": "Amritsar", "ludhiana": "Ludhiana", "patna": "Patna",
    "ranchi": "Ranchi", "jamshedpur": "Jamshedpur", "raipur": "Raipur", "imphal": "Imphal", "kohima": "Kohima", "aizawl": "Aizawl",
    "gangtok": "Gangtok", "srinagar": "Srinagar", "jammu": "Jammu", "shimla": "Shimla", "manali": "Manali", "udaipur": "Udaipur",
    "jodhpur": "Jodhpur", "agra": "Agra", "varanasi": "Varanasi", "banaras": "Varanasi", "kanpur": "Kanpur",
    "prayagraj": "Prayagraj", "allahabad": "Prayagraj", "ghaziabad": "Delhi NCR", "faridabad": "Delhi NCR",
    "greater noida": "Delhi NCR", "nashik": "Nashik", "aurangabad": "Aurangabad", "kolhapur": "Kolhapur", "puducherry": "Puducherry",
    "pondicherry": "Puducherry", "darjeeling": "Darjeeling", "ooty": "Ooty", "leh": "Leh", "bikaner": "Bikaner", "ajmer": "Ajmer",
    "panaji": "Goa", "panjim": "Goa", "thane": "Thane", "bhilai": "Bhilai", "hubballi": "Hubballi", "belagavi": "Belagavi",
    "tiruchirappalli": "Tiruchirappalli", "trichy": "Tiruchirappalli", "kota": "Kota", "gwalior": "Gwalior", "jabalpur": "Jabalpur",
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

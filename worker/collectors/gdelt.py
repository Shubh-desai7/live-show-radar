"""GDELT DOC 2.0 news search as an UNCONFIRMED discovery channel (free; terms: cite GDELT, https://www.gdeltproject.org).

Each query is an RSS-format artlist URL. The worker reads it like any publisher feed (robots.txt honoured, slow per-host
delay, retry on 429): headlines are matched against the whole artist catalog and only produce unconfirmed reports through
the existing news extractor. GDELT is headline-level and noisy, so nothing from it is ever confirmed or alerted.
"""
from __future__ import annotations

from typing import List
from urllib.parse import quote

HOST = "api.gdeltproject.org"
RECHECK_MINUTES = 360          # each query at most every 6 hours

_TOPIC = '(concert OR tour OR festival OR "live in")'
_QUERIES = [
    '(India OR Bengaluru OR Bangalore OR Mumbai OR Delhi) (concert OR "live in concert") (announced OR announces OR tickets) sourcecountry:IN',
    '("India tour" OR "India dates" OR "India leg" OR "India debut") sourcecountry:IN',
    '(Bengaluru OR Bangalore OR Hyderabad OR Chennai) ' + _TOPIC + ' (announced OR announces OR tickets) sourcecountry:IN',
    '(Mumbai OR Pune OR Goa OR Ahmedabad) ' + _TOPIC + ' (announced OR announces OR tickets) sourcecountry:IN',
    '(Delhi OR Gurugram OR Kolkata OR Jaipur) ' + _TOPIC + ' (announced OR announces OR tickets) sourcecountry:IN',
    '("music festival" OR "music fest") (India OR Goa OR Shillong OR Pune) (lineup OR announced) sourcecountry:IN',
]


def query_url(query: str, timespan: str = "3d", maxrecords: int = 250) -> str:
    return ("https://%s/api/v2/doc/doc?query=%s&mode=artlist&format=rss&maxrecords=%d&timespan=%s&sort=datedesc"
            % (HOST, quote(query, safe=""), maxrecords, timespan))


def gdelt_urls() -> List[str]:
    return [query_url(q) for q in _QUERIES]


def is_gdelt(url: str) -> bool:
    return ("//" + HOST + "/") in url

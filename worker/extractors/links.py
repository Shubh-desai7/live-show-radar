"""Page-level booking link fallback for an artist's OWN site.

Some official tour pages list shows without a link per row but publish one ticketing link for the Indian leg.
We use it only when it is unambiguous: exactly one distinct Indian-ticketing link on the page. Links to non-Indian
platforms (e.g. Ticketmaster for US dates) are ignored because every show we store is in India.
"""
from __future__ import annotations

from typing import Optional, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

INDIA_TICKETING = ("bookmyshow.com", "insider.in", "district.in", "paytminsider.com", "ticketgenie.in", "townscript.com",
                   "bookmyshowlive.com", "ticketmaster.in", "tickets.in", "skillbox.in", "eventsnow.com")


def _host_matches(host: str) -> bool:
    host = host.lower()
    return any(host == d or host.endswith("." + d) for d in INDIA_TICKETING)


def unique_india_ticket_link(html: str, base_url: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: Set[str] = set()
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"].strip())
        p = urlparse(url)
        if p.scheme in ("http", "https") and _host_matches(p.hostname or "") and len(p.path.strip("/")) > 0:
            found.add(url.split("#")[0])
    return next(iter(found)) if len(found) == 1 else None

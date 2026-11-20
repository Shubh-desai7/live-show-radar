"""News publishers whose RSS feeds are fetched by the worker. robots.txt is honoured for every feed (checked
2026-11-20: all of these allow readers). Items are only headline-level reports, so every show derived from them is
UNCONFIRMED. Add a feed here (or as a `publisher_rss` row in `sources`) only after checking its robots.txt and terms."""
from __future__ import annotations

PUBLISHER_FEEDS = [
    "https://rollingstoneindia.com/feed/",
    "https://www.thehindu.com/entertainment/music/feeder/default.rss",
    "https://indianexpress.com/section/entertainment/music/feed/",
    "https://www.hindustantimes.com/feeds/rss/entertainment/music/rssfeed.xml",
    "https://timesofindia.indiatimes.com/rssfeeds/1081479906.cms",
]

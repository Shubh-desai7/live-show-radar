# Source research (2026-11-21)

Policy: only sources whose robots.txt AND terms permit automated reading; never bypass bot protection; no paid services without owner approval.

| Source | Category | robots.txt | Terms | Static/JSON-LD | Verdict |
|---|---|---|---|---|---|
| District (district.in) | ticketing | `*` allowed on event pages; events sitemap advertised | ToS (updated 2026-11-01) forbids "scrapes or crawls" and limits content to personal non-commercial use | n/a | **Not permitted.** Needs written permission. |
| BookMyShow | ticketing | `*` allows event pages; sitemaps advertised (events.xml) | T&C forbid "unlimited or wholesale reproduction, copying of the content for commercial or non-commercial purposes"; no commercial exploitation | n/a (scraper vendors describe a bot challenge and need Indian residential proxies) | **Not permitted** without permission. No public API/partner programme found. |
| Apify BMS/District actors (6 reviewed) | paid scrapers | n/a | n/a | n/a | **Rejected**: $1.2-5 per 1,000 results, residential Indian proxies required (evades bot protection), tiny user counts. |
| Google News RSS | news | `Disallow: /` for generic bots | personal feed-reader use only | n/a | Not viable (unchanged). |
| Google Alerts RSS | news | feeds under www.google.com/alerts/feeds: not verified | not verified | n/a | Needs the owner's Google account and a terms check; not built. |
| GDELT DOC 2.0 | news index | robots.txt 404 (allowed) | free incl. commercial; cite GDELT; 1 request per 5 s | RSS/JSON, headline only | **Built, yield unmeasured**: every request got HTTP 429 on 2026-11-21 from this network even 20 s apart; retried once per run, skipped for 6 h. Check its yield from the Actions runner. |
| JamBase Data API | event database | n/a | Developer plan: $0, non-commercial, 1,000 calls/month, attribution; overage $0.05/call | JSON | **Needs the owner's trial key**; India coverage never stated, must be measured first. |
| Ticketmaster Discovery | event database | n/a | free key; storage limited to "reasonable periods" | JSON | India not listed in coverage: unlikely. Untested. |
| Bandsintown / Songkick / Seated | artist tools | n/a | artist-account or consent only | n/a | Not viable for an aggregator. |
| Eventbrite search API | | | shut down in 2019 | | Not viable. |
| Rolling Stone India feeds | publisher | allowed | | RSS | Live (see CLAUDE.md). |
| Homegrown, Bandwagon, billboard.in feeds | publisher | | | | 0 items / 404 / DNS failure. |

## Permission request template (BookMyShow and District)
Send from the owner's own address (the app must not impersonate anyone):

> Subject: Request for permission / data access: non-commercial concert alert app
>
> Hello, I run Live Show Radar (https://live-show-radar-lac.vercel.app), a free, non-commercial app that alerts fans in India when artists they follow announce shows. We link every show to the official ticketing page on your site and do not sell tickets.
> We would like written permission, or an official feed/API, to read publicly listed concert titles, artists, dates, venues, cities and event URLs from [BookMyShow / District] at most a few times a day, identify ourselves with a clear user-agent, honour robots.txt, store only these basic facts, and always send users to your page to buy.
> Please tell us whether a feed, partner API or written licence is available, and under what conditions. Thank you.

Contact routes found: none published for data access. District/Eternal: legal@zomato.com is the only listed legal contact (the API address api@zomato.com concerns the Zomato restaurant API); BookMyShow: no contact found, use its corporate "Contact us" page.

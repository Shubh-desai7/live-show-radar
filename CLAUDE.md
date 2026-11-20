# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

**All 11 implementation steps are done and the app is live: https://live-show-radar-lac.vercel.app** (Vercel Hobby, project `live-show-radar`; repo https://github.com/Shubh-desai7/live-show-radar, public; Supabase project `scekuxvjyuzmrxwcrrdo`). Verified on 2026-11-20: CI green (web job; worker tests on Python 3.9 and 3.12); both scheduled workflows ran on GitHub with the real secrets and the live DB (no-ops, DB empty); the production site serves `/` and `/login`, redirects signed-out `/dashboard` to `/login`, the Telegram webhook answers 401 without the secret, and the Telegram webhook is registered (`getWebhookInfo`: correct URL, no errors). Earlier steps were verified against the live DB with throwaway users and fixture sites (all deleted).

**Real Telegram delivery:** the owner signed up on the live site and linked Telegram (1 user, 1 linked chat). A throwaway test alert ("General sale opens in about 2 hours: ZZ TEST ARTIST (ignore)") was sent through the real worker and Telegram's API accepted it (`delivery_status = sent`) **and the owner confirmed it arrived on their phone** (end-to-end real delivery verified, 2026-11-20). **Not yet verified (be honest about these):** (1) a *scheduled* (cron-triggered, not hand-run) reminder arriving on its own; (2) public email signup with confirmation (Supabase free email is rate-limited); (3) real-site coverage is thin: see "Real sources evaluated" below (one real source is live; the worker only reads static HTML); (4) Google OAuth and an in-app notification inbox were never built. **Token rotation (done 2026-11-20):** the Telegram bot token was exposed in a terminal during setup, so the owner revoked it in BotFather; the new token is in `.env.local`, the GitHub secret `TELEGRAM_BOT_TOKEN` and the Vercel env var (production redeployed). **Gotcha learned:** BotFather `/revoke` also clears the registered webhook; after any token rotation re-run `npm run telegram:webhook -- set <production URL>` and check with `-- info`, and redeploy so Vercel picks up the new env var. The stack below is the approved stack; change it only for a genuine technical incompatibility and record it in the Decisions log.

**Maintenance rule (this file is the handover document):** update it in the same change whenever a decision, command, table, data source, notification rule or design token changes. Keep `README.md` in sync. Never document a command that is not actually configured.

## Product: Live Show Radar

A personalised concert discovery and alert web app for music fans who follow multiple artists. It finds upcoming live shows across India and notifies users about announcements, presales, ticket sales and booking deadlines. Launch city: **Bengaluru**; other Indian cities are selectable.

**Permanently out of scope:** payments and ticket booking. Users buy on the external ticketing platform via a link.

User journey: Landing (bold pitch, sign up/log in) → Onboarding (artists via search + manual add, cities, notification prefs) → Dashboard (followed-artist shows, newly announced, presales/sales/deadlines, manage artists/cities/prefs) → Event page (artist, city, venue if known, date, announcement source, confirmation status, ticket link, presale/general-sale dates, early-bird if known).

### Verification states (core domain invariant)
| State | Meaning | Shown to users? |
|---|---|---|
| **Confirmed** | Official artist, promoter or ticketing source | Yes; eligible for normal event notifications |
| **Unconfirmed** | Credible secondary source, awaiting official confirmation | Yes, always labelled unconfirmed, never as official |
| **Rumoured** | Weak evidence / speculation | **Never presented as an event**; stored internally for later verification |

Never invent event information. Accuracy beats visual appeal. A status change (e.g. unconfirmed → confirmed, or cancellation) must trigger an event-update alert.

## Technology stack (approved)

**Frontend:** Next.js (App Router), TypeScript, React, Tailwind CSS, shadcn/ui (selective use only), Lucide React icons. Custom Spotify-Wrapped-inspired dark UI; expressive, modern display typography suited to music culture (specific fonts pending approval, see Open decisions).

**Backend (web):** Next.js server functionality (Server Components/Actions) and Route Handlers in TypeScript where an HTTP API is needed (e.g. Telegram webhook).

**Data collection/processing:** Python worker using `requests`, `beautifulsoup4`, `feedparser` and the standard library.

**Data:** Supabase PostgreSQL with Row Level Security; Supabase Auth.

**Hosting/ops:** Vercel (web), Supabase (DB + auth), GitHub (repo), GitHub Actions (scheduled Python workers), Telegram Bot API (notifications).

**Cost rule:** zero-cost prototype (Vercel Hobby, Supabase Free, GitHub Actions within quota, open-source libs). Do **not** add paid infrastructure, subscriptions, paid APIs or paid AI services without first explaining why and getting approval. Free tiers carry no production uptime guarantee: account for Supabase free-project inactivity pausing, Vercel Hobby limits, and GitHub Actions quotas, cron delay and automatic disabling of scheduled workflows after repository inactivity.

**Source constraints:** permitted sources are official artist sites, promoter sites, Google News RSS, and newsletters only after research validates them. No Instagram scraping. Do not assume ticketing platforms have public APIs. Respect site terms and robots.txt/access restrictions (record blocked sources via `sources.access_status`). No Spotify API in the MVP. Manual artist entry must work without any external artist API; MusicBrainz may be evaluated as an optional search source but must never be a critical dependency.

## Architecture

Two connected components that share only the Supabase database.

### A. Web application (`app/`, `components/`, `lib/`)
Landing, sign-up/login, onboarding, artist selection/management, city preferences, personalised dashboard, event details, ticket info, notification preferences, profile. Uses the Supabase anon key + user session so RLS applies. The service-role key is used only in server-only code, never in client bundles.

### B. Background discovery engine (`worker/`)
Runs independently of the frontend, as scheduled GitHub Actions jobs. Pipeline:
1. Read tracked artists and permitted sources from Supabase.
2. Collect from configured public sources.
3. Extract relevant content.
4. Identify possible concert announcements.
5. Match against tracked artists.
6. Extract city, venue, date when available.
7. Classify confidence (confirmed / unconfirmed / rumoured).
8. Detect duplicates (same show from several sources → one event).
9. Verify and update event info.
10. Extract ticket/presale info where available.
11. Save to Supabase.
12. Trigger the notification workflow.

Retain, for every item: source URL, publication timestamp, first-seen timestamp, detection timestamp. Uses the service-role key via env vars (GitHub Secrets in CI) and bypasses RLS, so it must scope every write deliberately.

### C. Notifications
Telegram Bot API first. Users link Telegram to their web account via a **secure, single-use, expiring token** (deep link to the bot; the webhook handler verifies `TELEGRAM_WEBHOOK_SECRET`, consumes the token, stores `profiles.telegram_chat_id`). Alert types: new announcements, presale-registration reminders, presale-opening reminders, general-sale reminders, event updates/cancellations.

Reminder engine rules:
- Schedule reminders **24h and 2h before** each ticket deadline, **only when timing is reliable**.
- Store all timestamps in **UTC**; render in the user's `profiles.timezone`.
- Prevent duplicates via the unique `notifications.idempotency_key`.
- Record delivery status; retry failures safely (idempotent, bounded attempts).
- **Do not promise real-time delivery**: GitHub Actions cron can be delayed. Never describe delivery as exact.

## Database (Supabase, `supabase/migrations/`)

Core tables and columns (use proper FKs, indexes, unique constraints):
- `profiles`: user_id, display_name, telegram_chat_id, timezone, created_at
- `artists`: artist_id, artist_name, official_website, metadata, created_at
- `user_artists`: user_id, artist_id, priority, created_at
- `user_cities`: user_id, city, country
- `sources`: source_id, source_type, source_url, artist_id, access_status, last_checked_at
- `events`: event_id, artist_id, event_name, city, venue, event_date, confidence, status, booking_url, source_id, source_published_at, first_seen_at, detected_at, last_verified_at, created_at, updated_at
- `tickets`: ticket_id, event_id, presale_registration_deadline, presale_opening, general_sale_opening, early_bird_status, booking_url, last_updated_at
- `notification_preferences`: user_id, new_event_alerts, presale_alerts, ticket_sale_alerts, event_update_alerts
- `notifications`: notification_id, user_id, event_id, notification_type, scheduled_at, sent_at, delivery_status, idempotency_key
- `raw_source_logs`: log_id, source_id, source_url, raw_content_reference, collected_at, processing_status

**RLS (enabled on every table):** users read/write only their own rows in `profiles`, `user_artists`, `user_cities`, `notification_preferences`, `notifications` (read-only for notifications). `artists`, `events`, `tickets` are readable by authenticated users; `events`/`tickets`/`sources`/`raw_source_logs` are written only by the service role; `raw_source_logs` and `sources` are not exposed to users. Rumoured events must not be readable by user-facing queries. Store no unnecessary personal data.

Approved schema additions, implemented in the migration: `telegram_link_tokens` (hashed token, user_id, expires_at, used_at; service role only); `notifications.channel / reminder_offset_minutes (1440 or 120) / attempts / last_error`; `tickets.timing_reliable`. Other implementation choices: a trigger creates `profiles` + `notification_preferences` rows on signup; unique indexes enforce one artist name (case-insensitive) and one event per artist+city+date; any authenticated user may insert an artist (manual entry must work), which is an abuse surface to revisit.

## Repository structure

```
live-show-radar/
├── app/                 # Next.js App Router: (auth)/ dashboard/ artists/ events/ settings/ api/ layout.tsx page.tsx
├── components/          # ui/ (shadcn) dashboard/ events/ artists/
├── lib/                 # supabase/ auth/ notifications/ utils/
├── worker/              # Python: collectors/ extractors/ matching/ verification/ notifications/ database/ main.py
├── supabase/migrations/
├── .github/workflows/   # scheduled worker + CI
├── public/  tests/  .env.example  CLAUDE.md  package.json  requirements.txt  README.md
```
Keep a clear separation between frontend, backend operations and background workers. Adjust only if technically necessary and record it here. (The project currently lives in the `Tickets tracker` folder; the tree above is the target layout at the repo root.)

## Development commands

Frontend (all configured in `package.json`):
```bash
npm install
npm run dev          # http://localhost:3000 (a "web" entry exists in .claude/launch.json)
npm run build
npm run lint
npm run typecheck    # runs `next typegen` first: it generates the global LayoutProps/PageProps types
npm test             # vitest, tests/**/*.test.ts
npx vitest run tests/status.test.ts      # single file
npx vitest run -t "rumoured"             # single test by name
```

Python worker (dev machine has Python 3.9.6: keep code 3.9-compatible, hence `from __future__ import annotations`, no `match`, `Optional[...]` not `X | None`):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m worker.main --dry-run      # discover: fetch + extract, write nothing
python -m worker.main [--limit N]    # discover (real run; reads .env.local, or real env vars in CI)
python -m worker.main remind [--dry-run]   # schedule 24h/2h reminders + deliver due notifications
pytest                               # all worker tests (pytest.ini: tests/worker, pythonpath .)
pytest tests/worker/test_http.py::test_robots_disallow_is_respected_and_page_never_requested   # single test
```
Do not add `tests/worker/__init__.py`: it makes pytest shadow the `worker` package.

## Supabase CLI
Installed as a dev dependency (`npx supabase`). Config in `supabase/config.toml`, migrations in `supabase/migrations/` (the first is `20261120000000_core_schema.sql`: all tables, constraints, indexes, RLS, signup trigger).
```bash
npx supabase login                                   # once, interactive (opens browser)
npx supabase link --project-ref scekuxvjyuzmrxwcrrdo # once; prompts for the DB password
npx supabase db push --remote                        # apply pending migrations to the live project
```
**CLI v3 defaults to a local Docker database: always pass `--remote` to target the live project** (add `--yes` to skip the prompt). Never edit an applied migration; add a new timestamped file. Privileges are explicit: `anon` has no table access; `authenticated` gets only the grants listed in the migration (e.g. users may update `profiles.display_name`/`timezone` but **not** `telegram_chat_id`; `sources` exposes only `source_id, source_type, source_url, artist_id` so `access_status` stays internal).

To run SQL against the live DB: `npx supabase db query --remote --yes "<sql>"` (`--yes` is required for writes; read-only queries use `--read-only`). Test users can be created in Dashboard → Authentication → Users → Add user (Auto confirm) to bypass email.

## Auth (as built)
Email + password via Supabase Auth (Google OAuth still planned). Server Actions in `lib/auth/actions.ts` (`signIn`, `signUp`, `signOut`); `app/auth/callback/route.ts` exchanges the email-confirmation code. Clients: `lib/supabase/client.ts` (browser), `server.ts` (cookies, RLS applies), `admin.ts` (service role, bypasses RLS, server-only). `proxy.ts` (Next 16's replacement for `middleware.ts`) refreshes the session and redirects signed-out users from `/dashboard /artists /events /settings /onboarding`; it is only an optimistic check, so server code must call `requireUser()` (`lib/auth/session.ts`, uses `getUser()`) before touching data. Supabase free built-in email is heavily rate-limited; for heavier testing disable "Confirm email" or add SMTP (would be a cost decision).

## Environment variables

**Supabase project (created 2026-11-20):** name `live-show-radar`, project ref `scekuxvjyuzmrxwcrrdo`, URL `https://scekuxvjyuzmrxwcrrdo.supabase.co`, region Singapore (ap-southeast-1), Free plan. The dashboard uses the new key model: the *publishable key* (`sb_publishable_…`) goes in `NEXT_PUBLIC_SUPABASE_ANON_KEY` and the *secret key* (`sb_secret_…`) in `SUPABASE_SERVICE_ROLE_KEY`; legacy anon/service_role keys are retired in early 2027. Auth: Site URL `http://localhost:3000`, redirect allow-list `http://localhost:3000/**` (add the Vercel URL at deploy time).

The worker also reads `WORKER_ALLOW_LOCAL=1` (optional, local tests only).

`.env.example` holds placeholders (copy to `.env.local`; never commit `.env*` with real values; keep comments on their own line, never after a value):
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_BOT_TOKEN`, `NEXT_PUBLIC_APP_URL`, `TELEGRAM_WEBHOOK_SECRET`.

Only `NEXT_PUBLIC_*` values may reach the browser. The service-role key, bot token, DB credentials and auth secrets are server/worker-only; in GitHub Actions they come from GitHub Secrets.

## Frontend conventions (as built)
- Next.js **16** with `cacheComponents` and `partialPrefetching` enabled in `next.config.ts`; Tailwind **v4** (CSS-first config in `app/globals.css`, no `tailwind.config`). `AGENTS.md` (generated by Next) says this Next differs from older versions: read `node_modules/next/dist/docs/` before using unfamiliar APIs. With `cacheComponents`, runtime/dynamic data access needs a `<Suspense>` boundary.
- Design tokens live in `@theme` in `app/globals.css` (colours `ink/line/bone/mist/volt/grape/hotpink/ember/acid`, fonts `font-display` = Bricolage Grotesque, `font-sans` = Inter). `.grain` (noise overlay) is on `<body>`; `.halftone` is a decoration utility. Reduced-motion is respected globally.
- `lib/utils/cn.ts` is the class-merge helper. shadcn/ui is **not yet initialised**; run its CLI when the first real form/dialog needs it (selective use).
- Domain rules live in `lib/events/status.ts` (`isUserVisible`, `isOfficiallyConfirmed`); UI components only accept `confirmed | unconfirmed`, so rumoured events cannot be rendered by type.

## Onboarding and settings (as built)
- A user is "onboarded" when they follow >=1 artist and track >=1 city (`isOnboarded` in `lib/artists/validate.ts`); no extra DB flag. `/dashboard` redirects incomplete users to `/onboarding`; signup/login land on `/onboarding`.
- Pages: `/onboarding` (artists, cities, alert prefs), `/artists`, `/settings` (cities, prefs), `/dashboard`. Shared UI: `components/app-shell.tsx`, `components/artists/artist-picker.tsx`, `components/settings/{city-picker,preferences-form}.tsx`.
- Server actions: `lib/artists/actions.ts` (`searchArtists`, `followArtist` which find-or-creates the artist so manual entry needs no external API, `unfollowArtist`), `lib/settings/actions.ts` (`toggleCity`, `savePreferences`). Reads go through `lib/settings/queries.ts`. All run as the user, so RLS applies.
- Cities are a fixed list in `lib/cities.ts` (Bengaluru first); custom cities are not supported yet.
- **cacheComponents gotcha:** every user-specific server read must sit under a `<Suspense>` boundary, and `requireUser()` starts with `await connection()`. Without it dev mode reports "unstable value Date.now() while prerendering" for `/dashboard` and `/onboarding`.
- Tests: `tests/artists.test.ts`, `tests/status.test.ts` (`npm test`).

## Discovery worker (as built, step 6)
Pipeline in `worker/pipeline.py`; entry `worker/main.py`. Layers: `database/client.py` (thin PostgREST client on `requests`, service-role key, bypasses RLS) -> `database/repo.py` (the only interface the pipeline uses; faked in tests) ; `collectors/http.py` (`PoliteFetcher`); `extractors/` (`cities.py`, `dates.py`, `html_events.py`, `feeds.py`); `matching/artists.py`. `verification/classify.py` holds the confidence rules; `notifications/` is an empty package for step 10.
- **Flow:** tracked artists = artists followed by >=1 user. Each tracked artist's `official_website` is auto-registered as an `artist_website` source. Sources (`artist_website`, `promoter_website`) are checked oldest-`last_checked_at` first, up to `--limit` (default 40). A page hash is stored in `raw_source_logs.raw_content_reference` (`sha256:...`); unchanged pages are skipped. Events are deduped on artist+city+date (unique index backstop: 409 is treated as "existing").
- **Politeness/safety (all tested):** identifying User-Agent `LiveShowRadarBot/0.1` (no personal contact details); robots.txt fetched per host and obeyed (404/410 = allowed; 401/403/5xx/network error = treated as restricted); redirects followed manually with robots re-checked per hop; >=2 s between requests to a host; 2 MB cap; html/xml/text content types only; HTTP 401/403/429 -> `sources.access_status = blocked` and never retried within a run; private/loopback hosts refused unless `WORKER_ALLOW_LOCAL=1` (tests/local fixtures only).
- **Extraction rules (never invent):** a block yields a candidate only with exactly one recognised Indian city and exactly one date **with an explicit year**; venue is never guessed; ambiguous blocks are skipped. City aliases (Bangalore, Bombay, Gurugram...) normalise to the same names as `lib/cities.ts`. Promoter pages (no `artist_id`) require the artist's name in the same block.
- **Classification (`verification/classify.py`, tested):** `confirmed` = the artist's own `artist_website`, or a `promoter_website` block that names the artist unambiguously; `unconfirmed` = secondary sources (`newsletter`, `google_news_rss`; none enabled yet) with an unambiguous name; `rumoured` = everything weaker, including any ambiguous-name match. Confidence only moves up automatically (`is_upgrade`); a confirmed event is never downgraded. An upgrade also makes the better source the event's `source_id` and fills a missing `booking_url` (official sources only).
- **Matching (`matching/artists.py`):** names are normalised (case, accents, `&`/and, punctuation); whole-word match. A single-word name that is <=4 letters or in `COMMON_WORDS` is *ambiguous*: it only matches with concert context (live/concert/tour/...) and is capped at `rumoured`. Extend `COMMON_WORDS` as real data shows false positives. Consequence: very short real artist names (e.g. "Zed") can never be auto-confirmed from promoter pages; they are still confirmed from their own site.
- **Verification/updates:** re-seeing an event on a non-rumoured source sets `last_verified_at`; unchanged pages bulk-refresh `last_verified_at` for that source's scheduled events (`touch_verified`). Only a `confirmed`-level source can set `cancelled`/`postponed` (explicit words in the same block: cancelled/canceled/called off, postponed/rescheduled); a status is never reverted automatically, and a cancellation notice for a show we never tracked is ignored. Page disappearance is NOT treated as cancellation (too many false positives).
- **Change events:** `pipeline.run(..., on_change=callback)` emits `EventChange(kind=new_event|confirmed|status_changed, ...)` only for non-rumoured events, once per transition. Step 10 will hook notification creation here (idempotency key per event + kind/status).
- **Google News RSS is deliberately disabled.** Its robots.txt says `Disallow: /` for generic bots, and the feed itself states it is only for rendering results in a personal feed reader for personal, non-commercial use. Using it would conflict with the rule "do not violate website terms or access restrictions". `extractors/feeds.py` (generic RSS/Atom parsing) exists for other permitted publisher feeds, but no feed collector is wired into the pipeline yet. Open decision for the owner: accept Google's terms risk, or use specific publisher feeds that permit syndication (would need a new `source_type` migration).
- **Not done yet:** promoter/artist sources must be inserted into `sources` by hand (service role); there is no admin UI. Real-site extraction quality is unknown until pointed at real pages.

## Structured-data extraction (JSON-LD, built after launch)
`worker/extractors/jsonld.py` reads `<script type="application/ld+json">` blocks for schema.org events (any `*Event` / `Festival`; handles `@graph`, arrays, `ItemList`, nested nodes); `worker/extractors/page.py::extract_all` merges these with the text extractor (structured wins per city+date; the text block can fill a missing booking link). Tests: `tests/worker/test_jsonld.py` plus pipeline tests (115 Python tests).
- **Uses:** exact `venue` and `event_name` (stored on `events`; the UI already shows them), `offers.url` as booking link, `performer`/`headliner` and the event name for artist matching on promoter pages, `eventStatus` (cancelled / postponed / rescheduled), and `offers.validFrom` as the sale start: it becomes `general_sale_opening`, or `presale_opening` when the offer name looks like a presale/early-access/members offer; early-bird offers only set `early_bird_status`. A `validFrom` is *precise* only with a time **and** a zone, so `timing_reliable` follows the same rules as the text extractor. `validFrom` is ambiguous by nature (sites may use it for a different tier), which is why reliability also needs an official source.
- **Rules (never invent):** an event needs a valid start date and exactly one recognised Indian city (found in the location's address/name); online-only events are skipped; HTML entities are decoded and strings are sanitised (control characters stripped, lengths capped, non-http(s) URLs dropped); placeholder performers ("Organization", "Person", "TBA", ...) are ignored because event plugins emit them. Max 200 events per page.
- **Past shows are skipped** for all extractors (`past_skipped` stat): never create or alert on a show that already happened.
- **Official sources fill gaps:** an existing event missing `venue`, `event_name` or `booking_url` is completed by a confirmed-level source.

## Save workflow, booking links, 30-minute checks, site discovery (owner request, 2026-11-20)
- **Explicit Save (web):** the artist picker (`components/artists/artist-picker.tsx`), the A-Z browser and the city picker no longer write on every click. Edits are staged locally (dashed "unsaved" chips, removals struck through), a sticky bar shows "N unsaved changes / Save artists | Save cities / Discard" (`components/save-bar.tsx`), and leaving the page with unsaved edits warns. One batch server action each: `saveArtistChanges({addIds, addNames, removeIds})` in `lib/artists/actions.ts` (ids validated as UUIDs, typed names find-or-create, upsert with `ignoreDuplicates`, max 300 changes) and `saveCities(cities)` in `lib/settings/actions.ts` (replaces the set). Pure helpers `lib/artists/selection.ts` (+ tests). Verified on production with a throwaway user: nothing reached the DB before Save (0 rows), then 3 artists and 2 cities saved. Preferences keep their own Save button. The old per-click actions (`followArtist`, `followArtistById`, `toggleCity`) still exist but are unused by the UI.
- **Official booking link everywhere:** shown as an "Official booking link" button on every dashboard card and, prominently, at the top of the event page (hostname shown, `target=_blank rel="noopener noreferrer"`); the page says "No booking link has been published yet" when none exists. Telegram messages now say `Official booking link: <url>` (or that none is published yet, for announcements and reminders). Link sources, best first: the show's own link (JSON-LD `offers.url`/`url`, or an anchor in the same block), then **page-level fallback on an artist's OWN site only**: if the page contains exactly one distinct Indian-ticketing link (`extractors/links.py`: BookMyShow, Insider, District, Paytm Insider, ...; non-Indian platforms such as Ticketmaster are ignored because every stored show is in India; bare homepages ignored) it is used for Indian shows that lack their own. Never invented; a link is only as official as the source page that published it.
- **Stale warning:** the event page warns when a scheduled show has not been re-confirmed on its official page for 48 hours (`events.last_verified_at`).
- **Every 30 minutes:** `discover.yml` cron is `7,37 * * * *` (timeout 25 min); `remind.yml` stays `*/15`. Each `discover` run: (1) site discovery for up to 18 artists, (2) re-checks followed artists' pages and promoter pages (those not checked in the last 25 minutes; up to 300 per run), (3) up to 25 other catalog artists' pages that have not been checked for 24 h, (4) creates alerts, delivers due notifications. GitHub cron is best effort: not yet proven to fire on its own (see below).
- **Catalog-wide matching ("already fetched"):** the pipeline matches promoter pages against the whole featured catalog plus followed artists (`repo.catalog_artists`), and crawls every catalog artist's registered pages (daily for non-followed), so events for an artist usually exist before anyone follows them; alerts still go only to followers. Real example: Sunburn's "Anyma Presents Aeden" (Mumbai, 2026-11-22) was ingested for Anyma although nobody follows Anyma.
- **Automatic official-site discovery (`worker/discovery/sites.py`, `worker/collectors/musicbrainz.py`):** MusicBrainz (free, optional, never critical; 1 request/s, retries on 503 `Retry-After`, UA `LiveShowRadar/0.1 (<repo URL>)`, no personal details) proposes a homepage only for a **single exact-name match with score >= 95** and an "official homepage" link that is not social/streaming/link-in-bio. The site is then fetched politely (robots honoured) and **must mention the artist's name** or it is rejected (`unverified`): real examples of why: MusicBrainz returned `adityajagdhane.in` for "Arijit Singh" and a site for "A. R. Rahman" that does not mention him. A verified site is saved to `artists.official_website` and registered as `artist_website` sources: the homepage plus up to two listing pages whose URL path is a short slug like `/tour`, `/events`, `/shows`, `/live` (article-style URLs are ignored). Outcomes and retry windows are stored in `artists.metadata` (`site_status`, `site_checked_at`, `site_retry_after`): ok 7 d, none 30 d, ambiguous/unverified 60 d, blocked 30 d, error 1 d. Followed artists are processed first (10/run), then the catalog by `featured_rank` (8/run), so the 502-artist catalog is covered in about a day of runs. Measured yield on real artists: roughly half get a verified site; **far fewer have a tour list that static HTML can expose** (many use JavaScript widgets). Coverage is reported honestly in the dashboard panel; it is a best-effort net, not a guarantee of "all events for every artist".
- **Reprocessing on improvement:** `config.EXTRACTOR_VERSION` is part of each page fingerprint (`sha256:<hash>|v<version>`); bump it when extraction logic changes and every page is re-processed once even if its content is unchanged. (This is what filled Diljit's Ahmedabad booking link: `https://in.bookmyshow.com/events/diljit-dosanjh-aura-india-tour-2026-ahmedabad/et42470qp8`.)
- **Live results at time of writing:** 19 registered sources after ~4 local passes (verified sites for e.g. Coldplay, Taylor Swift, Seedhe Maut, Divine, Shreya Ghoshal, Don Diablo, Yiruma, Anitta, Dua Lipa); 3 India shows in the DB (Diljit Ahmedabad 2026-11-21, Anyma Mumbai 2026-11-22, The Chainsmokers Bengaluru 2026-12-20). Most followed artists simply have no readable India show right now.
- **Operational notes:** `python -m worker.main discover` accepts `--skip-sites`; a dry run still calls MusicBrainz and fetches sites but writes nothing. Two user accounts exist in the DB now; only throwaway test accounts created by the assistant were ever deleted.

## Why a user can see no shows (coverage reality, 2026-11-20)
Following artists or adding cities never triggers discovery; those only filter what is already in the database. Shows exist only if one of the registered `sources` lists them. At the time this section was written there were only 2 sources; see the section above for the automatic site discovery that has since been added. The owner follows ~42 artists in 4 cities and 1 of those artists has a source, so most followed artists can never produce a show until more sources exist. Third-party articles report more shows (e.g. Diljit in Mumbai/Bengaluru, Fred again.. in Delhi/Mumbai/Bengaluru in December 2026), but those are not confirmed by any source we may read, so the worker does not create them. The dashboard now says this ("How we find your shows": number of sources, their hosts, how many followed artists have their own official page) and no longer claims discovery is switched off.
- **Ways to widen coverage (decisions for the owner):** (a) research each followed artist's official page one by one (yield so far ~1 in 3; JS widgets and robots blocks stop the rest); (b) more promoter sites that allow crawling and publish structured events; (c) a licensed events API with its own key and terms (e.g. Ticketmaster Discovery, Bandsintown): new external integration, needs the owner's approval, terms review, a key, and has poor India coverage; (d) newsletters/publisher RSS feeds that permit syndication (`extractors/feeds.py` exists but is not wired into the pipeline; would need a new `source_type`). Do not scrape ticketing platforms, and do not enable Google News RSS (see "Discovery worker").
- **Unproven:** at the time of writing GitHub had not yet fired any cron-scheduled run (only manual `workflow_dispatch` runs), about 50 minutes after the workflows were created; GitHub delays new schedules, so check `gh run list --workflow remind.yml` for `schedule` events before trusting scheduled alerts.

## Real sources evaluated (2026-11-20)
- **Live (promoter): `https://sunburn.in/events/`** (Sunburn, an Indian festival promoter; WordPress Events Calendar plugin with JSON-LD). Its robots.txt is `User-Agent: * / Disallow:` (everything allowed); no terms page could be found (legal URLs return 404), so the owner may veto it. Verified end to end: a throwaway user following The Chainsmokers in Bengaluru got "Sunburn Arena ft. The Chainsmokers", Bengaluru, 2026-12-20, venue "Bangalore", confirmed, with the event link; the other Sunburn events were correctly ignored (nobody follows those artists). That event remains in the DB as real data; the throwaway user was deleted.
- **Live:** `https://www.diljitdosanjh.com/tour/` (Diljit Dosanjh's official site, linked via `artists.official_website`; robots.txt allows it; 1 request per run). First real ingestion: Diljit Dosanjh, Ahmedabad, 2026-11-21, `confirmed`, with a real Telegram alert delivered. The page is static HTML with rows like "Nov 21 Ahmedabad Saturday, November 21, 2026 · Narendra Modi Stadium"; it lists only one upcoming India date at the moment, so more will appear if the page changes (a changed page hash is re-extracted).
- **Prateek Kuhad (`prateekkuhad.com`, genuine official site):** the tour list is injected by a JavaScript Songkick widget, so the shows are not in the HTML; the worker cannot read it and Songkick must not be scraped. Not added. Would need an API with permission or a different source.
- **Aditya Gadhvi:** `adityagadhvi.com` returned `robots_disallowed`: honoured, not added. `adityagadhvi.in` was an empty page (not verified as his). Third-party listings (BookMyShow, District, Insider, Sulekha, AXS, Bandsintown) are ticketing platforms: not scraped.
- **Also probed and rejected:** `district.in/events` (a ticketing platform: its robots.txt allows crawling and it has JSON-LD, but we do not scrape ticketing platforms by policy; its terms were not reviewed), `in.bookmyshow.com` (blocks bots), `insider.in`, `nh7.in`, `thehummingtree.in` (robots disallow, honoured), Rolling Stone India (a magazine, not an event source), and festival sites with no machine-readable events on their home pages (Echoes of Earth, Magnetic Fields, Bluefrog, Lollapalooza India: no event pages found).
- **General lesson:** artist sites differ a lot; static `/tour` pages and JSON-LD work, JS widgets and robots-blocked sites do not. Always dry-check a candidate with `PoliteFetcher` + `extract_candidates` before adding a source, and verify the site is genuinely the artist's (page title) before trusting it.
- **Worker bugs found by real sites and fixed:** robots.txt that answers with a redirect (`prateekkuhad.com` -> `www`) was wrongly treated as restricted (now follows up to 5 redirects per RFC 9309, loops fail safe); pages without a declared charset were decoded as Latin-1 (mojibake), now UTF-8 with cp1252 fallback. 100 Python tests.
- **Data note:** the owner's misspelled follow "diljit doshanj" was merged into the featured "Diljit Dosanjh" artist. User-typed misspellings never match featured artists; consider fuzzy matching in the picker.

## Performance and artist discovery (post-launch fixes, 2026-11-20)
- **Lag root cause and fix:** Vercel functions defaulted to `iad1` (Washington DC) while Supabase is in Singapore, so every page paid several US<->Singapore round trips (visible as `x-vercel-id: bom1::iad1`). `vercel.json` now pins `"regions": ["sin1"]` (now `bom1::sin1`). Measured afterwards on production: warm signed-in pages ~250-700 ms; a cold start after idle can still take ~1-1.5 s (Hobby plan, no keep-warm). Keep the function region next to the database; if the Supabase region ever changes, change `vercel.json` too.
- **Artist catalog (current):** 502 curated, well-known artists (173 `india`, 329 `world`), names only (no claims about tours), generated from `scripts/gen_artist_catalog.py` into migration `20261120140000_artist_catalog.sql`. **Edit the script and add a NEW migration for changes; never hand-edit an applied migration.** Columns: `artists.featured`, `artists.region` (`india|world`), `artists.featured_rank` (1..48 = editorial prominence order used by the "popular" row; others 1000). It is a starting set, not "all artists": anyone can still be added by typing a name. Misspellings typed by users never match catalog entries.
- **A-Z browser:** `/artists/browse` (`components/artists/artist-browser.tsx`, pure helpers in `lib/artists/browse.ts`, tests in `tests/browse.test.ts`): letter navigation (accent-insensitive; digits/symbols under `#`), All/India/World filter, search, optimistic one-tap follow/unfollow via `followArtistById` (by id, so names like `P!nk` or `KR$NA` are safe). Linked from the "Popular on Live Show Radar" block in the artist picker. Verified on production with a throwaway user (502 artists, 26 letter sections, filters 173/329, follows persisted).
- **Matching guard extended:** more common-word names (Ghost, Tool, Muse, Kiss, ...) and ambiguous phrases (Take That, The Script, Indian Ocean, ...) are treated as ambiguous (concert context required, capped at `rumoured` on promoter pages).
- **Earlier empty-catalog fix (superseded by the above):** `artists.featured` plus a seeded starter list of 42 well-known artists (names only, no claims about tours) in migration `20261120120000_featured_artists.sql`. Onboarding and `/artists` show a tap-to-follow "Popular on Live Show Radar" row from `suggested_artists()`.
- **Recommendations (honest scope):** `suggested_artists(max_rows)` (security definer, executable by `authenticated` only) ranks by co-follow (artists followed by >= 3 users who share an artist with you), then overall popularity, then the featured list. Thresholds of 3 mean it never reveals what an individual follows. It is **not taste-based**: there is no listening data (no Spotify API in the MVP), and with few users it is effectively the featured list. The UI says so.
- **Security tightening:** users can now insert an artist with only `artist_name` (column-level grant). Previously they could set `official_website` (which the worker crawls) and `metadata` via the API, an abuse path. Featured/official_website are set by the service role only.

## Deployment and operations (step 11)
- **Vercel:** project `live-show-radar` is linked to the GitHub repo (`.vercel/` is git-ignored), so every push to `main` redeploys production. Production env vars (set with `vercel env add ... production`; secrets are stored as sensitive and cannot be read back): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_APP_URL` (= the production URL; it is inlined at build time, so redeploy after changing it), `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_BOT_USERNAME`. **Gotcha:** `vercel link` appends `VERCEL_OIDC_TOKEN` to `.env.local` and `.env*` to `.gitignore`; the latter would re-ignore `.env.example`, so revert it (`git checkout -- .gitignore`) and delete the token line.
- **Supabase auth URLs:** Site URL = the production URL; redirect allow-list has `http://localhost:3000/**` and `https://live-show-radar-lac.vercel.app/**`.
- **Telegram webhook:** registered with `npm run telegram:webhook -- set https://live-show-radar-lac.vercel.app` (check with `-- info`). Re-run `set` if the production URL ever changes.
- **GitHub Actions** (`.github/workflows/`): `ci.yml` (push/PR: web lint+typecheck+test+build with placeholder env; worker pytest on Python 3.9 / ubuntu-22.04 and 3.12 / ubuntu-latest, because ubuntu-latest no longer ships 3.9), `discover.yml` (cron `17 1,7,13,19 * * *`), `remind.yml` (cron `*/15 * * * *`). Both worker workflows also have `workflow_dispatch` (`gh workflow run remind.yml`). Repo secrets: `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN` (write-only; set with `gh secret set NAME`). **Never use bash-only `${!var}` in zsh when scripting secrets**: it silently sets empty values.
- **Free-tier realities:** GitHub cron is best effort (delays, skipped runs) and scheduled workflows are auto-disabled after 60 days without repo activity (push something or re-enable in the Actions tab). The public repo has unlimited Actions minutes; the 15-minute cadence would exceed the 2,000 free minutes if the repo were made private. A free Supabase project pauses after ~1 week of inactivity; every worker run touches the DB, which keeps it awake, but if the Actions schedule stops, so does that. Vercel Hobby is for non-commercial use. None of these services guarantee production uptime.
- **Tooling on the owner's Mac:** `gh` lives at `~/bin/gh` (not on the terminal's PATH); `npx vercel` and `npx supabase` work from the repo. `gh` needed the `workflow` scope to push workflow files (`gh auth refresh -h github.com -s workflow`).
- **Operating it (what still needs a human):** add real discovery sources as rows in `sources` (type `artist_website` or `promoter_website`) via `npx supabase db query --remote --yes "insert into public.sources ..."`; artists' `official_website` is auto-registered once an artist is followed. Check each site's terms and robots.txt first. There is no admin UI.

## Reminder engine (as built, step 10)
Code: `worker/notifications/engine.py` (scheduling + delivery), `messages.py` (plain-text rendering), `telegram.py` (sender), repo methods in `worker/database/repo.py`, CLI in `worker/main.py`. Tests: `test_engine.py`, `test_messages.py`, `test_telegram.py` (97 Python tests total).
- **CLI:** `python -m worker.main discover [--dry-run] [--limit N]` (default; discovery + event alerts + deliver due) and `python -m worker.main remind [--dry-run]` (schedule reminders + deliver due). Plan for CI: `remind` every ~15 min, `discover` a few times a day. Without `TELEGRAM_BOT_TOKEN` notifications are created but not delivered. Output stats: delivery keys are prefixed `notif_` (the pipeline also has a `failed` key for sources).
- **Who is notified:** only users with Telegram linked who follow the artist, track the event's city (case-insensitive) and have the matching preference on (`new_event_alerts`; `presale_alerts` for registration+opening; `ticket_sale_alerts` for general sale; `event_update_alerts` for cancel/postpone). Users without Telegram get nothing yet (no web inbox).
- **Reminders:** only for `confirmed`, `scheduled` events whose `tickets.timing_reliable` is true, at **24 h and 2 h before** each of presale registration deadline / presale opening / general sale. `scheduled_at` is UTC. A reminder whose time passed less than `CATCHUP_GRACE` (60 min) ago is still sent immediately (cron delay); older ones are skipped, and a moment already past gets none. Scheduling is derived from DB state each run and idempotent via `notifications.idempotency_key` (`reminder:{event}:{type}:{offset}:{user}:{moment-epoch}`), so a moved moment yields new rows and the old pending ones are cancelled (`superseded`); a cancelled event, unlink, or opt-out also cancels pending reminders; a **cancelled** row is revived to pending if it becomes desired again (unlink -> relink), while sent/failed rows are never revived.
- **Event alerts:** created immediately from the pipeline's `on_change` for **confirmed** events only: `new_event` (also when an event becomes confirmed), `event_cancelled`, `event_update` (postponed). Key: `new_event:{event}:{user}` / `event_update:{event}:{status}:{user}`. Events found before a user linked Telegram do not alert them retroactively (reminders for future moments still schedule).
- **Delivery:** re-validates at send time (still linked, still follows, preference on, event still confirmed/eligible, moment still ahead, timing still reliable) and **cancels instead of sending** otherwise. The attempt counter is claimed first by an optimistic lock (`attempts N -> N+1`, so two workers can't both send); delivery is at-least-once (a crash after sending but before marking could repeat a message). Retries: Telegram 429/5xx/network -> `scheduled_at = now + max(retry_after, backoff 5/15/45/120 min)`, up to `MAX_ATTEMPTS` (5) then `failed`; 403/"chat not found" -> `failed` and the chat is unlinked (`profiles.telegram_chat_id = null`); other 4xx -> `failed`. `sent_at`, `delivery_status`, `attempts`, `last_error` are recorded.
- **Messages:** plain text (no markup), times in the user's `profiles.timezone` (`zoneinfo`; `tzdata` is in requirements), exact moment + "in about N hours", ticket link if known, and "we don't sell tickets" footer. Never claims real-time delivery; GitHub Actions cron is best effort.
- **Known limits:** no digest/rate cap per user; no early-bird reminders (early-bird deadlines are not extracted); unconfirmed events never alert.

## Telegram (as built, step 9)
- **Linking flow:** Settings -> "Connect Telegram" runs `createTelegramLink` (`lib/notifications/actions.ts`, service role): revokes the user's unused tokens, creates a 32-byte random token (43-char base64url), stores only its SHA-256 in `telegram_link_tokens` with a 15-minute expiry, and returns `https://t.me/<TELEGRAM_BOT_USERNAME>?start=<token>`. The user presses Start in a private chat; Telegram POSTs to `/api/telegram/webhook`.
- **Webhook (`app/api/telegram/webhook/route.ts`):** rejects with 401 unless `X-Telegram-Bot-Api-Secret-Token` matches `TELEGRAM_WEBHOOK_SECRET` (constant-time; always rejects if the secret is unset); 400 on bad JSON; otherwise always 200 (errors are logged without tokens or user content) so Telegram doesn't retry-storm. Logic lives in `lib/notifications/webhook.ts` (`handleUpdate`, dependency-injected, unit-tested) and `link-token.ts`; real DB/Telegram deps in `telegram-deps.ts`. Linking only works in **private** chats. The token is consumed by one atomic `UPDATE ... WHERE used_at IS NULL AND expires_at > now()`, so it works exactly once. A chat id belongs to one account (re-linking detaches it from any other profile first). `/stop` unlinks; other messages get a help reply.
- **Disconnect:** `disconnectTelegram` (service role, scoped to the signed-in user) because users have no UPDATE privilege on `profiles.telegram_chat_id`. The chat id never reaches the browser: the settings page only gets a `telegramLinked` boolean.
- `proxy.ts` excludes `/api/telegram` (no cookie session on webhook calls). The webhook handler needs `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` at runtime.
- **Sending alerts is the worker's job** (`worker/notifications/telegram.py`, unit-tested): classifies results as `sent | retry (429/5xx/network) | blocked (403, chat not found) | failed`, honours `retry_after`, and never puts the token in error text. The web app only sends the webhook's own replies (`telegram-api.ts`).
- **Commands:** `npm run telegram:webhook -- set https://<deployed-app>` (registers the webhook with the secret, `allowed_updates: ["message"]`), `-- info`, `-- delete`. Reads `.env.local`; never prints the token.
- **Setting up the bot (owner, one time):** in Telegram open @BotFather -> `/newbot` -> pick a name and a username ending in `bot` -> run `npm run telegram:setup` (hidden prompt; verifies the token with Telegram's `getMe` and writes `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME` to `.env.local` without printing the token), and add the same values to Vercel at deploy time. Until both are set the Settings page shows an honest "not set up" placeholder. Local development cannot receive webhooks without a public tunnel (not used, to avoid extra services).

## Ticket intelligence (as built, step 8)
`extractors/tickets.py` parses one event block; `verification/tickets.py` (`merge_tickets`, pure) merges into `tickets`; `pipeline.save_tickets` wires them. Both are unit-tested (`tests/worker/test_tickets.py`, `test_merge_tickets.py`, plus pipeline tests).
- **Extracts:** presale registration deadline (needs a deadline cue: by/before/until/closes/deadline; "registration opens" is deliberately ignored), presale opening, general sale opening, early-bird status (`available|ended|not_offered|unknown`). A moment needs an explicit date **with year**. First value per kind wins. A sale on/after the show date is discarded as a misread.
- **Precision and `timing_reliable`:** a moment is *precise* only with an explicit time. Bare times are read as **IST** (all supported cities are in India); IST/UTC/GMT/explicit offsets are understood; other zone abbreviations (EST, PST, ...) make it imprecise. A date-only moment is stored as 00:00 IST and is imprecise. `tickets.timing_reliable` is true only if **every** extracted moment is precise **and** the source is `confirmed`-level. The reminder engine (step 10) must only use rows with `timing_reliable = true`.
- **Merging:** a newly extracted value replaces the stored one (the official page is the truth); a value missing from the page never erases a stored one; `early_bird_status='unknown'` never overwrites a known status; reliability is recomputed only when the extraction contains moments. Tickets are written only from non-rumoured sources and never from a source weaker than the event's current confidence; cancelled events are not updated.
- **Show date vs sale dates:** `blank_ticket_dates` removes the dates that belong to sale wording before `html_events` counts dates, so a block with a show date plus sale dates still yields exactly one show date. Limitation: only text inside the same page block is read; sale info living on a separate ticketing page or a sibling element is not found. The worker never scrapes ticketing platforms.
- **UI:** `formatMoment(iso, tz, reliable)` in `lib/events/dashboard.ts`: verified moments show full local time; unverified show the IST date only plus "(time not confirmed)".

## Events UI (as built)
- Logic in `lib/events/dashboard.ts` (pure, unit-tested in `tests/dashboard.test.ts`): `upcomingDeadlines`, `nextDeadline`, `isNewlyAnnounced` (7 days from `first_seen_at`), `timeUntil`, `formatDateTime(iso, tz)`, `formatEventDate` (calendar date, no tz shift), `cityMatches` (case-insensitive; events with no city never match), `isUpcoming`. Reads in `lib/events/queries.ts` (`loadEventsForUser`, `loadEvent`) run as the user; RLS hides rumoured events and the code filters again defensively (`isUserVisible`, `toVisible`).
- `/dashboard` sections: "Don't miss these" (next 6 ticket moments, times in the user's `profiles.timezone`), "Just announced", "All upcoming shows". The card highlight ("Presale opens in 2h") appears **only when `tickets.timing_reliable`**; unreliable dates are shown with a "timing not verified" warning and will not get reminders. `/events/[id]` shows status explanation, venue/date, ticket moments, early-bird, an external "Book on the official site" link (target=_blank, rel=noopener noreferrer), source + published/first-seen/last-verified times, and the "we don't sell tickets" note. Invalid or rumoured ids render 404.
- Events whose `city` is null are not shown on the dashboard (they cannot match a chosen city). Revisit when the worker's city extraction is built.
- Login now redirects to `/dashboard`, which forwards incomplete users to `/onboarding`.

## Design system

"Dark mode. Loud colours. Big energy. Zero missed shows." Spotify Wrapped × underground posters, as inspiration only.
- **Palette:** near-black base; electric green primary; neon purple, vibrant pink, orange, acid yellow secondary; white/soft-grey text; bold gradients for featured events.
- **Language:** oversized expressive type, colourful concert cards, abstract shapes, grain/noise/halftone textures, stickers/badges, asymmetric layered layouts, subtle animation.
- Define colours, type scale and spacing as Tailwind theme tokens in one place; no ad-hoc hex values in components.
- Responsive desktop + mobile; keep contrast, focus states and reduced-motion support.
- Deadlines and announcements get the highest visual priority. Verification status is always visible on event cards.
- Never fake UI: any non-functional button/control must be clearly marked as a placeholder.
- Must never feel like: corporate SaaS dashboard, boring ticket site, plain notification tool, social feed, spam platform, cluttered UI.

## Implementation rules

Before coding: inspect the repo, read this file, check which config files exist, identify what is missing, update this file, then state a plan. Build incrementally, never the whole app in one pass. For every major piece: test it, fix errors before moving on, update this file if architecture changes, update README.md.

Sequence: 1 project setup + design system → 2 Supabase connection + auth → 3 onboarding + artist management → 4 dashboard + event discovery UI → 5 database integration → 6 Python discovery worker → 7 verification + matching → 8 ticket intelligence → 9 Telegram integration → 10 reminder engine → 11 testing + deployment.

## Approved decisions (2026-11-20, all proposals approved)
1. Repo visibility on GitHub (public = unlimited Actions minutes; private = 2,000 free min/month).
2. Display/body fonts (proposal: Bricolage Grotesque or Space Grotesk for display, Inter for body).
3. Test frameworks (proposal: Vitest + pytest).
4. Auth methods (proposal: email magic link/password plus Google OAuth).
5. Schema additions listed under Database.
6. Keep-alive approach for Supabase free-tier pausing (proposal: worker run touches the DB on every schedule).
7. Reminder cadence (proposal: reminder job every 15 minutes; discovery job a few times daily).

## Decisions log
- 2026-11-20: Project initialised from product brief.
- 2026-11-20: Stack and architecture approved (Next.js/TS/Tailwind/shadcn, Supabase, Python worker on GitHub Actions, Vercel, Telegram). All open-decision proposals approved as written (fonts, Vitest+pytest, email+Google auth, schema additions, keep-alive, 15-min reminder cadence). Repo visibility: public was listed first but is still to be chosen when the GitHub repo is created.
- 2026-11-20: Owner request implemented: explicit Save for artists/cities, official booking links on site and Telegram, 30-minute discovery, catalog-wide matching, MusicBrainz-based official-site discovery with strict verification.
- 2026-11-20: Telegram token rotated (webhook re-registered, GitHub + Vercel updated). Artist catalog expanded to 502 with an A-Z browser at `/artists/browse` after owner request ("all top artists in India and world, A to Z, and additional ones").
- 2026-11-20: JSON-LD event extraction built; Sunburn's events page added as the first promoter source (robots allow-all, no terms found); past shows are now skipped.
- 2026-11-20: First real source added (Diljit Dosanjh official tour page); first real event ingested and alerted. Fixed robots.txt-redirect and charset bugs found by real sites.
- 2026-11-20: Post-launch fixes after owner feedback ("no artists shown, no recommendations, too much lag"): functions moved to sin1, featured catalog + suggested artists added, artist insert narrowed to name only.
- 2026-11-20: Step 11 done: public GitHub repo, CI + scheduled workers on GitHub Actions, production on Vercel, Supabase auth URLs updated, Telegram webhook registered. Decisions: repo is public (owner's choice, for unlimited Actions minutes); CI checks Python 3.9 on ubuntu-22.04.
- 2026-11-20: Step 10 built (reminder engine). Decisions: only confirmed events alert; reminders need reliable timing; 60-min catch-up grace; 5 attempts with backoff; blocked chats are unlinked; cancelled reminders are revived when desired again; delivery is at-least-once.
- 2026-11-20: Step 9 built (Telegram linking, webhook, worker sender). Decisions: single-use hashed tokens with 15-min expiry, private chats only, webhook always answers 200 after auth, new env var `TELEGRAM_BOT_USERNAME`. Real-bot verification deferred until deployment.
- 2026-11-20: Step 8 done (ticket intelligence). Decisions: bare times are read as IST; reliability needs precise times for all moments plus an official source; date-only moments stored as 00:00 IST and displayed as dates only.
- 2026-11-20: Step 7 done (classification, matching ambiguity guard, verification, status detection). Decision: official-site and unambiguous promoter reports are confirmed; ambiguity or secondary-only evidence is capped lower.
- 2026-11-20: Step 6 done (worker pipeline). Decision: Google News RSS not enabled because of its robots.txt and feed terms; worker is robots-aware and uses artist/promoter sites only. Python 3.9 compatibility constraint noted.
- 2026-11-20: Step 4 done (dashboard sections, event cards, event detail page); verified with temporary fake rows, then deleted.
- 2026-11-20: Step 3 done (onboarding, artists, settings). Service-role key added to `.env.local`.
- 2026-11-20: Step 2 built: migration, Supabase clients, proxy.ts, login/signup/dashboard placeholder. Region note: project is in Singapore, not Mumbai. Step 2 started: Supabase project created, `.env.local` filled except the secret key (user adds it by hand), localhost redirect URL configured.
- 2026-11-20: Step 1 done. Scaffolded with create-next-app (Next 16.4, Tailwind 4); pinned `@types/node@^24` because vitest 5's peer range rejects `^20`. Not a git repo yet: init when the GitHub repo is created.

# Live Show Radar

Personalised concert discovery and alerts for music fans in India: follow artists, pick cities, and get notified about announcements, presales, ticket sales and deadlines. We never sell tickets; users buy on the official ticketing site.

Full context, architecture and decisions live in [CLAUDE.md](CLAUDE.md).

## Status
**Live:** https://live-show-radar-lac.vercel.app. All planned steps are built: design system, Supabase schema + email auth, onboarding and settings, event UI, the Python discovery worker (robots-aware, classification, ticket intelligence), Telegram linking, 24h/2h reminders, CI and scheduled workers. Real event data is just starting: one real official source is live (Diljit Dosanjh's tour page); more artist/promoter sources must be added case by case (see CLAUDE.md, "Real sources evaluated" and "Operating it"). A real Telegram delivery to a phone and email-confirmed signup have not been verified yet. Alerts run on GitHub Actions cron, which is best effort and never real-time.

## Run it
Requires Node 20+ (developed on Node 24).

```bash
npm install
npm run dev        # http://localhost:3000
npm run lint
npm run typecheck
npm test
npm run build
```

Copy `.env.example` to `.env.local` and fill it in once Supabase and Telegram are set up (step 2 onwards). Never commit real values.

## Python worker
Discovery worker (collect, extract, store). Needs Python 3.9+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m worker.main --dry-run   # fetch and extract, write nothing
python -m worker.main             # discover: real run (needs the Supabase env vars)
python -m worker.main remind      # schedule 24h/2h reminders and deliver due notifications
pytest                            # worker tests
```
It obeys robots.txt, rate-limits per host and classifies each event (confirmed / unconfirmed / rumoured), re-verifies known events, detects official cancellations, and extracts presale / general-sale dates (only exact, official times are marked reliable). Rumoured events stay internal. Google News RSS is intentionally not used; see CLAUDE.md.

## Telegram
Create a bot with @BotFather, then set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME` and `TELEGRAM_WEBHOOK_SECRET` (see `.env.example`). After deploying: `npm run telegram:webhook -- set https://<your-app>`. Details in CLAUDE.md.

## Artists
A curated catalog of 500+ well-known artists (India and world) can be browsed A to Z at `/artists/browse`. It is generated from `scripts/gen_artist_catalog.py`; anyone not listed can still be added by typing a name.

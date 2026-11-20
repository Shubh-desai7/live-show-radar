-- Extraction monitoring: per-run statistics, per-source results, and retained (rejected / incomplete) candidates.
-- All service-role only: no policies and no privileges for anon/authenticated. Admin pages read them server-side
-- after checking profiles.is_admin.

alter table public.profiles add column is_admin boolean not null default false;   -- users cannot set it (column-level update grants)

create table public.discovery_runs (
  run_id uuid primary key default gen_random_uuid(),
  command text not null,                              -- discover | remind | diagnose
  trigger text not null default 'manual',             -- schedule | manual | local
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  ok boolean,
  error text,
  stats jsonb not null default '{}'::jsonb
);
create index discovery_runs_started_idx on public.discovery_runs (started_at desc);

create table public.discovery_source_results (
  id bigint generated always as identity primary key,
  run_id uuid not null references public.discovery_runs (run_id) on delete cascade,
  source_id uuid references public.sources (source_id) on delete cascade,
  source_url text not null,
  status text not null,                               -- ok | unchanged | blocked | robots_disallowed | error
  detail text,
  candidates integer not null default 0,
  rejected integer not null default 0,
  events_new integer not null default 0,
  duration_ms integer
);
create index discovery_source_results_run_idx on public.discovery_source_results (run_id);

-- A candidate that was NOT turned into an event (incomplete, ambiguous, unmatched, past ...) kept for review/verification.
create table public.event_candidates (
  candidate_id uuid primary key default gen_random_uuid(),
  source_id uuid references public.sources (source_id) on delete cascade,
  stage text not null check (stage in ('extraction', 'matching', 'verification')),
  reason text not null,
  detail text,
  artist_hint text,
  event_name text,
  city_hint text,
  date_hint text,
  venue text,
  booking_url text,
  snippet text,
  content_key text not null,
  status text not null default 'open' check (status in ('open', 'promoted', 'discarded')),
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  times_seen integer not null default 1,
  unique (source_id, content_key)
);
create index event_candidates_reason_idx on public.event_candidates (reason, status);
create index event_candidates_seen_idx on public.event_candidates (last_seen_at desc);

alter table public.discovery_runs enable row level security;
alter table public.discovery_source_results enable row level security;
alter table public.event_candidates enable row level security;
revoke all on public.discovery_runs, public.discovery_source_results, public.event_candidates from anon, authenticated;

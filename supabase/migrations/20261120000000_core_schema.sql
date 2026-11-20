-- Live Show Radar: core schema, constraints, indexes and RLS.
-- Conventions: all timestamps are timestamptz (stored UTC). Every table has RLS enabled.
-- The service role (Python worker, server-only Next.js code) bypasses RLS; users never do.

-- ---------------------------------------------------------------- helpers
create function public.touch_updated_at() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end $$;

-- ---------------------------------------------------------------- profiles
create table public.profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  display_name text check (char_length(display_name) <= 80),
  telegram_chat_id bigint unique,           -- written only by the service role (Telegram linking)
  timezone text not null default 'Asia/Kolkata',
  created_at timestamptz not null default now()
);

create table public.notification_preferences (
  user_id uuid primary key references auth.users (id) on delete cascade,
  new_event_alerts boolean not null default true,
  presale_alerts boolean not null default true,
  ticket_sale_alerts boolean not null default true,
  event_update_alerts boolean not null default true
);

-- Every new auth user gets a profile and default preferences.
create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (user_id) values (new.id);
  insert into public.notification_preferences (user_id) values (new.id);
  return new;
end $$;
revoke execute on function public.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------- artists
create table public.artists (
  artist_id uuid primary key default gen_random_uuid(),
  artist_name text not null check (char_length(artist_name) between 1 and 120),
  official_website text check (official_website is null or official_website ~* '^https?://'),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create unique index artists_name_key on public.artists (lower(artist_name));

create table public.user_artists (
  user_id uuid not null references auth.users (id) on delete cascade,
  artist_id uuid not null references public.artists (artist_id) on delete cascade,
  priority smallint not null default 0,
  created_at timestamptz not null default now(),
  primary key (user_id, artist_id)
);
create index user_artists_artist_idx on public.user_artists (artist_id);

create table public.user_cities (
  user_id uuid not null references auth.users (id) on delete cascade,
  city text not null check (char_length(city) between 1 and 80),
  country text not null default 'India',
  primary key (user_id, city, country)
);

-- ---------------------------------------------------------------- sources
create table public.sources (
  source_id uuid primary key default gen_random_uuid(),
  source_type text not null check (source_type in
    ('artist_website', 'promoter_website', 'google_news_rss', 'newsletter')),
  source_url text not null unique check (source_url ~* '^https?://'),
  artist_id uuid references public.artists (artist_id) on delete cascade,
  access_status text not null default 'unvalidated' check (access_status in
    ('unvalidated', 'ok', 'blocked', 'robots_disallowed', 'error')),
  last_checked_at timestamptz
);
create index sources_artist_idx on public.sources (artist_id);

-- ---------------------------------------------------------------- events
create table public.events (
  event_id uuid primary key default gen_random_uuid(),
  artist_id uuid not null references public.artists (artist_id) on delete cascade,
  event_name text,
  city text,
  venue text,
  event_date date,
  confidence text not null check (confidence in ('confirmed', 'unconfirmed', 'rumoured')),
  status text not null default 'scheduled' check (status in
    ('scheduled', 'postponed', 'cancelled', 'completed')),
  booking_url text check (booking_url is null or booking_url ~* '^https?://'),
  source_id uuid references public.sources (source_id) on delete set null,
  source_published_at timestamptz,
  first_seen_at timestamptz not null default now(),
  detected_at timestamptz not null default now(),
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
-- Duplicate detection backstop: one event per artist, city and date.
create unique index events_dedupe_key on public.events (artist_id, lower(city), event_date)
  where city is not null and event_date is not null;
create index events_artist_date_idx on public.events (artist_id, event_date);
create index events_city_idx on public.events (lower(city));
create trigger events_touch before update on public.events
  for each row execute function public.touch_updated_at();

create table public.tickets (
  ticket_id uuid primary key default gen_random_uuid(),
  event_id uuid not null unique references public.events (event_id) on delete cascade,
  presale_registration_deadline timestamptz,
  presale_opening timestamptz,
  general_sale_opening timestamptz,
  early_bird_status text not null default 'unknown' check (early_bird_status in
    ('unknown', 'available', 'ended', 'not_offered')),
  booking_url text check (booking_url is null or booking_url ~* '^https?://'),
  -- Reminders are scheduled only when the worker marked the timings reliable.
  timing_reliable boolean not null default false,
  last_updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------- notifications
create table public.notifications (
  notification_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  event_id uuid references public.events (event_id) on delete cascade,
  notification_type text not null check (notification_type in
    ('new_event', 'presale_registration', 'presale_opening', 'general_sale',
     'early_bird', 'event_update', 'event_cancelled')),
  channel text not null default 'telegram' check (channel in ('telegram', 'web')),
  reminder_offset_minutes integer check (reminder_offset_minutes in (1440, 120)),
  scheduled_at timestamptz not null,
  sent_at timestamptz,
  delivery_status text not null default 'pending' check (delivery_status in
    ('pending', 'sent', 'failed', 'cancelled')),
  attempts smallint not null default 0,
  last_error text,
  idempotency_key text not null unique,   -- prevents duplicate notifications
  created_at timestamptz not null default now()
);
create index notifications_due_idx on public.notifications (scheduled_at)
  where delivery_status = 'pending';
create index notifications_user_idx on public.notifications (user_id, scheduled_at desc);

create table public.raw_source_logs (
  log_id uuid primary key default gen_random_uuid(),
  source_id uuid references public.sources (source_id) on delete cascade,
  source_url text not null,
  raw_content_reference text,
  collected_at timestamptz not null default now(),
  processing_status text not null default 'pending' check (processing_status in
    ('pending', 'processed', 'skipped', 'error'))
);
create index raw_source_logs_source_idx on public.raw_source_logs (source_id, collected_at desc);

-- Single-use Telegram linking. Only a hash of the token is stored; service role only.
create table public.telegram_link_tokens (
  token_hash text primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  expires_at timestamptz not null,
  used_at timestamptz
);
create index telegram_link_tokens_user_idx on public.telegram_link_tokens (user_id);

-- ---------------------------------------------------------------- RLS
alter table public.profiles enable row level security;
alter table public.notification_preferences enable row level security;
alter table public.artists enable row level security;
alter table public.user_artists enable row level security;
alter table public.user_cities enable row level security;
alter table public.sources enable row level security;
alter table public.events enable row level security;
alter table public.tickets enable row level security;
alter table public.notifications enable row level security;
alter table public.raw_source_logs enable row level security;
alter table public.telegram_link_tokens enable row level security;

-- Privileges: start from nothing for anon, then grant exactly what users need.
revoke all on all tables in schema public from anon, authenticated;

grant select on public.profiles to authenticated;
grant update (display_name, timezone) on public.profiles to authenticated;  -- NOT telegram_chat_id
grant select, update on public.notification_preferences to authenticated;
grant select, insert on public.artists to authenticated;
grant select, insert, delete on public.user_artists to authenticated;
grant update (priority) on public.user_artists to authenticated;
grant select, insert, delete on public.user_cities to authenticated;
grant select on public.events, public.tickets, public.notifications to authenticated;
grant select (source_id, source_type, source_url, artist_id) on public.sources to authenticated;
-- raw_source_logs and telegram_link_tokens: no user privileges at all (service role only).

create policy profiles_select_own on public.profiles for select to authenticated
  using (user_id = (select auth.uid()));
create policy profiles_update_own on public.profiles for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

create policy prefs_select_own on public.notification_preferences for select to authenticated
  using (user_id = (select auth.uid()));
create policy prefs_update_own on public.notification_preferences for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

create policy artists_select on public.artists for select to authenticated using (true);
create policy artists_insert on public.artists for insert to authenticated with check (true);

create policy user_artists_select_own on public.user_artists for select to authenticated
  using (user_id = (select auth.uid()));
create policy user_artists_insert_own on public.user_artists for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy user_artists_update_own on public.user_artists for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy user_artists_delete_own on public.user_artists for delete to authenticated
  using (user_id = (select auth.uid()));

create policy user_cities_select_own on public.user_cities for select to authenticated
  using (user_id = (select auth.uid()));
create policy user_cities_insert_own on public.user_cities for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy user_cities_delete_own on public.user_cities for delete to authenticated
  using (user_id = (select auth.uid()));

-- Rumoured events are internal: never readable by users.
create policy events_select_visible on public.events for select to authenticated
  using (confidence <> 'rumoured');
create policy tickets_select_visible on public.tickets for select to authenticated
  using (exists (select 1 from public.events e
                 where e.event_id = tickets.event_id and e.confidence <> 'rumoured'));

create policy sources_select on public.sources for select to authenticated using (true);

create policy notifications_select_own on public.notifications for select to authenticated
  using (user_id = (select auth.uid()));

-- JamBase Data API (licensed event database) becomes a source type. Everything derived from it is a secondary report:
-- classified Unconfirmed, never alerted. The Developer plan is non-commercial and requires attribution.
alter table public.sources drop constraint sources_source_type_check;
alter table public.sources add constraint sources_source_type_check
  check (source_type in ('artist_website', 'promoter_website', 'google_news_rss', 'newsletter', 'publisher_rss', 'jambase'));

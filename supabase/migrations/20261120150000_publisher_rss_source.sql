-- Publisher RSS feeds (news sites that allow automated readers) become a source type.
-- Everything derived from them is a secondary report: classified Unconfirmed, never confirmed, never alerted.
alter table public.sources drop constraint sources_source_type_check;
alter table public.sources add constraint sources_source_type_check
  check (source_type in ('artist_website', 'promoter_website', 'google_news_rss', 'newsletter', 'publisher_rss'));

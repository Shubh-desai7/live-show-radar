-- Featured artist catalog, popularity-based suggestions, and tighter artist inserts.

alter table public.artists add column featured boolean not null default false;

-- Users may only supply an artist NAME. They could previously set official_website (which the worker crawls)
-- and metadata through the API; that is an abuse path, so those columns are no longer insertable by users.
revoke insert on public.artists from authenticated;
grant insert (artist_name) on public.artists to authenticated;

-- Starter catalog so onboarding is never an empty box. Names only: no claims about tours or events.
insert into public.artists (artist_name, featured)
select n, true
from unnest(array[
  'Arijit Singh', 'A. R. Rahman', 'Diljit Dosanjh', 'AP Dhillon', 'Karan Aujla', 'Badshah', 'Divine',
  'Yo Yo Honey Singh', 'Prateek Kuhad', 'Anuv Jain', 'Ritviz', 'Nucleya', 'Sunidhi Chauhan', 'Shreya Ghoshal',
  'Armaan Malik', 'Jubin Nautiyal', 'Neha Kakkar', 'Vishal Mishra', 'Anirudh Ravichander', 'Amit Trivedi',
  'Sonu Nigam', 'Shankar Mahadevan', 'Hanumankind', 'Seedhe Maut', 'Prabh Deep', 'MC Stan', 'Lost Stories',
  'Zaeden', 'Raghu Dixit Project', 'Indian Ocean', 'Parikrama', 'Thaikkudam Bridge',
  'Coldplay', 'Ed Sheeran', 'Imagine Dragons', 'Maroon 5', 'Bryan Adams', 'Enrique Iglesias', 'Lauv',
  'The Chainsmokers', 'Martin Garrix', 'Alan Walker'
]) as n
on conflict (lower(artist_name)) do update set featured = true;

-- Suggestions for the signed-in user, excluding artists they already follow.
-- Ranking: artists followed by >= 3 users who share an artist with you (co-follow), then overall popularity, then the
-- curated list. The thresholds mean the function never reveals what any individual follows. It is NOT taste-based
-- (no listening data is used); it is "popular on Live Show Radar" until there are enough users.
create function public.suggested_artists(max_rows integer default 12)
returns table (artist_id uuid, artist_name text)
language sql stable security definer set search_path = '' as $$
  with me as (select ua.artist_id from public.user_artists ua where ua.user_id = auth.uid()),
  peers as (
    select ua.user_id from public.user_artists ua
    where ua.artist_id in (select artist_id from me) and ua.user_id <> auth.uid()
    group by ua.user_id
  ),
  co as (
    select ua.artist_id, count(distinct ua.user_id) as n
    from public.user_artists ua
    where ua.user_id in (select user_id from peers) and ua.artist_id not in (select artist_id from me)
    group by ua.artist_id having count(distinct ua.user_id) >= 3
  ),
  pop as (select ua.artist_id, count(*) as n from public.user_artists ua group by ua.artist_id)
  select a.artist_id, a.artist_name
  from public.artists a
  left join co on co.artist_id = a.artist_id
  left join pop on pop.artist_id = a.artist_id
  where a.artist_id not in (select artist_id from me)
    and (a.featured or co.n is not null or coalesce(pop.n, 0) >= 3)
  order by coalesce(co.n, 0) desc, coalesce(pop.n, 0) desc, a.featured desc, a.artist_name
  limit least(greatest(max_rows, 1), 50)
$$;
revoke execute on function public.suggested_artists(integer) from public, anon;
grant execute on function public.suggested_artists(integer) to authenticated;

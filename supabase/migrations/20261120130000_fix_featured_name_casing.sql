-- A user had typed this artist in lowercase before the featured catalog existed; use the proper spelling.
update public.artists set artist_name = 'Prateek Kuhad' where lower(artist_name) = 'prateek kuhad';

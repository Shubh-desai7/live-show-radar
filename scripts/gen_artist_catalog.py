"""Generates supabase/migrations/20261120140000_artist_catalog.sql from the curated lists below.
Names only (no claims about tours or events). Well-known current or recently active acts. Run: python3 scripts/gen_artist_catalog.py"""
import re

# Editorial prominence order for the "popular" suggestions (rank 1..N). Everything else gets rank 1000.
TOP = ["Arijit Singh", "Diljit Dosanjh", "A. R. Rahman", "Coldplay", "Ed Sheeran", "AP Dhillon", "Karan Aujla", "Taylor Swift",
       "Prateek Kuhad", "Anuv Jain", "Shreya Ghoshal", "Badshah", "Divine", "Imagine Dragons", "Dua Lipa", "Nucleya", "Ritviz",
       "The Weeknd", "Sunidhi Chauhan", "Yo Yo Honey Singh", "Martin Garrix", "Sonu Nigam", "Jubin Nautiyal", "Armaan Malik",
       "Anirudh Ravichander", "Metallica", "BTS", "Maroon 5", "Neha Kakkar", "Shankar Mahadevan", "Bryan Adams", "The Chainsmokers",
       "Alan Walker", "Calvin Harris", "David Guetta", "Post Malone", "Billie Eilish", "Bruno Mars", "Drake", "Eminem",
       "Enrique Iglesias", "Lauv", "Hanumankind", "Seedhe Maut", "MC Stan", "Amit Trivedi", "Vishal Mishra", "Aditya Gadhvi"]

INDIA = """Aditya Gadhvi|Agam|Ajay-Atul|Alka Yagnik|Amaal Mallik|Amit Trivedi|Amrinder Gill|Ammy Virk|Anirudh Ravichander|Ankit Tiwari|Ankur Tewari|Anoushka Shankar|Anupam Roy|Anuv Jain|AP Dhillon|A. R. Rahman|Arijit Singh|Armaan Malik|Asees Kaur|Asha Bhosle|Avadhoot Gupte|Avial|Babbu Maan|Badshah|Benny Dayal|Bijibal|Bloodywood|Bohemia|Brodha V|B Praak|Chandrabindoo|Chinmayi|D. Imman|Darshan Raval|Devi Sri Prasad|Dhruv|Dhvani Bhanushali|Dino James|Diljit Dosanjh|Divine|Dualist Inquiry|Emiway Bantai|Euphoria|Falguni Pathak|Fotty Seven|Geeta Rabari|Ghulam Ali|Gippy Grewal|Gopi Sundar|Gurdas Maan|Gurnam Bhullar|Guru Randhawa|G. V. Prakash Kumar|Hanumankind|Hariharan|Haricharan|Hariprasad Chaurasia|Harrdy Sandhu|Harris Jayaraj|Harshdeep Kaur|Ikka|Ilaiyaraaja|Indus Creed|Indian Ocean|Jass Manak|Jasleen Royal|Jassie Gill|Javed Ali|Jazzy B|Job Kurian|Jonita Gandhi|Jordan Sandhu|Jubin Nautiyal|Kailash Kher|Kanika Kapoor|Karan Aujla|Karthik|Kaushiki Chakraborty|Kinjal Dave|Kohra|KR$NA|Kryptos|K. S. Chithra|Kulwinder Billa|Kumar Sanu|Lifafa|Lost Stories|Lucky Ali|M. M. Keeravani|Mame Khan|Mankirt Aulakh|MC Stan|Mika Singh|Mithoon|Mohammed Irfan|Mohit Chauhan|Monali Thakur|Motherjane|Naezy|Neeti Mohan|Neha Kakkar|Nimrat Khaira|Nooran Sisters|Nucleya|Osman Mir|Palak Muchhal|Papon|Parikrama|Parmish Verma|Parvaaz|Pentagram|Peter Cat Recording Co.|Prabh Deep|Prateek Kuhad|Pritam|Raftaar|Raghu Dixit Project|Rahul Deshpande|Rekha Bhardwaj|Ritviz|Rishab Rikhiram Sharma|Sachin-Jigar|Salim-Sulaiman|Sam C. S.|Sandunes|Sanam|Santhosh Narayanan|Satinder Sartaaj|Seedhe Maut|Shaan|Shankar Mahadevan|Sharry Maan|Shilpa Rao|Shreya Ghoshal|Shubh|Shubha Mudgal|Shweta Mohan|Sid Sriram|Silk Route|Skyharbor|Sonu Nigam|Soulmate|Stebin Ben|Sukhwinder Singh|Sunanda Sharma|Sunidhi Chauhan|Sushin Shyam|Swarathma|Taba Chake|Talat Aziz|Tanishk Bagchi|Thaikkudam Bridge|Thaman S|The Local Train|Thermal and a Quarter|Tony Kakkar|Tulsi Kumar|Udit Narayan|Vijay Prakash|Vijay Yesudas|Vishal Dadlani|Vishal Mishra|Vishal-Shekhar|When Chai Met Toast|Yo Yo Honey Singh|Yuvan Shankar Raja|Zaeden|Amjad Ali Khan|Demonic Resurrection|Advaita|Aastha Gill|Payal Dev|Nikhita Gandhi|Dualist Inquiry""".split("|")

WORLD = """5 Seconds of Summer|50 Cent|A$AP Rocky|AC/DC|Above & Beyond|Adele|Aerosmith|Afrojack|Alan Walker|Alesso|Alicia Keys|Alok|Amelie Lens|Anderson .Paak|Andrea Bocelli|Anitta|Anyma|Architects|Ariana Grande|Armin van Buuren|Arctic Monkeys|Arooj Aftab|Asake|Asim Azhar|Atif Aslam|ATEEZ|Avenged Sevenfold|Axwell & Ingrosso|Ayra Starr|Abida Parveen|Ali Sethi|Ali Zafar|Bad Bunny|Benson Boone|Beyoncé|Billie Eilish|Billy Joel|Black Coffee|BLACKPINK|Blink-182|Boris Brejcha|Bon Jovi|Bring Me the Horizon|Britney Spears|Bruce Springsteen|Bruno Mars|Bryan Adams|Bryson Tiller|BTS|Burna Boy|Calvin Harris|Camila Cabello|Camilo|Cardi B|Carl Cox|Central Cee|Charlie Puth|Charlotte de Witte|Chappell Roan|Childish Gambino|Chris Brown|Chris Stapleton|Christina Aguilera|Coldplay|Daddy Yankee|Daniel Caesar|Dave|Davido|David Guetta|Deadmau5|Deep Purple|Def Leppard|Demi Lovato|Diana Krall|Dimitri Vegas & Like Mike|Diplo|Doja Cat|Don Diablo|Dream Theater|Drake|Dua Lipa|Eagles|Ed Sheeran|Elton John|Eminem|ENHYPEN|Enrique Iglesias|Eric Clapton|Eric Prydz|Excision|EXO|Fall Out Boy|Fleetwood Mac|Flume|Foo Fighters|Frank Ocean|Fred again..|Future|G-Dragon|Ghost|Giveon|Gojira|Gracie Abrams|Green Day|Guns N' Roses|Halsey|Hans Zimmer|Hardwell|Harry Styles|H.E.R.|Hozier|Il Divo|Illenium|Imagine Dragons|Iron Maiden|ITZY|IU|J Balvin|J. Cole|Jack Johnson|James Blunt|Jason Mraz|Jay-Z|Jennifer Lopez|Jhené Aiko|Jimin|Joe Hisaishi|John Legend|John Mayer|Jonas Brothers|Judas Priest|Jungkook|Justin Bieber|Kacey Musgraves|Kanye West|Karol G|Katy Perry|Keith Urban|Kendrick Lamar|Kenny G|Khalid|KISS|Kings of Leon|Kygo|Lady Gaga|Lana Del Rey|Lauv|Le Sserafim|Lenny Kravitz|Lewis Capaldi|Liam Gallagher|Lil Wayne|Linkin Park|Lisa|Lizzo|Lorde|Lost Frequencies|Luis Fonsi|Luke Combs|Madeon|Maluma|Marshmello|Martin Garrix|Maroon 5|Mark Knopfler|Mastodon|Megadeth|Metallica|Metro Boomin|Michael Bublé|Miley Cyrus|Monsta X|Morgan Wallen|Muse|My Chemical Romance|NCT 127|Nicki Minaj|Nicky Romero|Niall Horan|Nina Kraviz|Norah Jones|NewJeans|Oasis|Oliver Heldens|Olivia Rodrigo|Opeth|OneRepublic|Ozuna|Paramore|Paul McCartney|Passenger|Pearl Jam|Peso Pluma|Peggy Gou|Phil Collins|P!nk|Porter Robinson|Post Malone|Psy|Queens of the Stone Age|Radiohead|Rahat Fateh Ali Khan|Rammstein|Red Hot Chili Peppers|Red Velvet|Rema|Ricky Martin|Rihanna|Robin Schulz|Rod Stewart|Roger Waters|Rosé|Sabaton|Sabrina Carpenter|Sam Smith|Santana|Scorpions|Selena Gomez|Seventeen|Shakira|Shawn Mendes|Shinee|Sia|Skepta|Skrillex|Slipknot|Snoop Dogg|Solomun|Steve Aoki|Sting|Stormzy|Stray Kids|SZA|Sleep Token|System of a Down|Tale of Us|Tame Impala|Tate McRae|Taylor Swift|Teddy Swims|Tems|The 1975|The Chainsmokers|The Killers|The Lumineers|The Rolling Stones|The Weeknd|Tiësto|Timmy Trumpet|Tomorrow X Together|Tool|Travis Scott|Troye Sivan|Twenty One Pilots|TWICE|Tyler, the Creator|U2|Usher|Vampire Weekend|Vini Vici|W&W|Wizkid|Yanni|Yiruma|Zayn|Zedd|Zach Bryan|aespa|Anyma|Mumford & Sons|Jessie J|Rita Ora|Ellie Goulding|Cigarettes After Sex|Mac DeMarco|Billie Joe Armstrong|Bastille|Hailee Steinfeld|Alessia Cara|Meghan Trainor|Ne-Yo|Akon|Pitbull|Flo Rida|Sean Paul|Shaggy|Jason Derulo|Ludacris|Travis Barker|blackbear|Joji|Rich Brian|keshi|Conan Gray|Sigrid|Sigur Rós|Måneskin|Imagine Dragons|Linkin Park|Ludovico Einaudi|Lindsey Stirling|2Cellos|Kodaline|The Script|Westlife|Boyzone|Backstreet Boys|NSYNC|Take That|Spice Girls|Jonas Brothers|Nickelback|Seether|Evanescence|Breaking Benjamin|Disturbed|Korn|Limp Bizkit|Papa Roach|Godsmack|Five Finger Death Punch|Trivium|Lamb of God|Parkway Drive|Amon Amarth|Behemoth|Dimmu Borgir|Children of Bodom|In Flames|Dark Tranquillity|Nightwish|Within Temptation|Epica""".split("|")

def norm(n): return re.sub(r"\s+", " ", n.strip())
seen, rows = set(), []
def add(name, region):
    n = norm(name)
    if not n or n.lower() in seen: return
    seen.add(n.lower()); rows.append((n, region))

# World first would let 'Coldplay' etc. win; India list owns Indian names, so add India first, then world.
for n in INDIA: add(n, "india")
for n in WORLD: add(n, "world")
rank = {norm(n).lower(): i + 1 for i, n in enumerate(TOP)}
assert all(norm(n).lower() in seen for n in TOP), [n for n in TOP if norm(n).lower() not in seen]

def q(s): return "'" + s.replace("'", "''") + "'"
values = ",\n  ".join("(%s, %s, %s)" % (q(n), q(r), rank.get(n.lower(), 1000)) for n, r in sorted(rows, key=lambda x: x[0].lower()))
sql = f"""-- Curated starter catalog (generated by scripts/gen_artist_catalog.py; edit the script, not this file).
-- Names only: no claims about tours or events. Well-known current or recently active acts. {len(rows)} artists.
alter table public.artists add column region text check (region in ('india', 'world'));
alter table public.artists add column featured_rank integer;

insert into public.artists (artist_name, featured, region, featured_rank)
select v.name, true, v.region, v.rank
from (values
  {values}
) as v(name, region, rank)
on conflict (lower(artist_name)) do update
  set featured = true, region = excluded.region, featured_rank = excluded.featured_rank;

-- Suggestions now break ties by editorial prominence (featured_rank) before falling back to the alphabet.
create or replace function public.suggested_artists(max_rows integer default 12)
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
  order by coalesce(co.n, 0) desc, coalesce(pop.n, 0) desc, a.featured_rank asc nulls last, a.artist_name
  limit least(greatest(max_rows, 1), 50)
$$;
"""
open("supabase/migrations/20261120140000_artist_catalog.sql", "w").write(sql)
print("artists:", len(rows), "| india:", sum(1 for r in rows if r[1]=="india"), "| world:", sum(1 for r in rows if r[1]=="world"), "| ranked:", len(rank))

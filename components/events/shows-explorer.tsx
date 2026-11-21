"use client";

import { ExternalLink, MapPin, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Reveal } from "@/components/motion/reveal";
import { cityCounts, filterShows, groupByDate, placeLabel, type Show } from "@/lib/events/explore";
import { bookingLabel } from "@/lib/events/status";
import { cn } from "@/lib/utils/cn";

const sourceLabel: Record<string, string> = {
  artist_website: "Artist's official site", promoter_website: "Promoter's official site", publisher_rss: "News report", google_news_rss: "News report", newsletter: "Newsletter", jambase: "Concert database",
};

function fmtDate(d: string | null) {
  if (!d) return "Date to be announced";
  return new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(d + "T00:00:00Z"));
}

export function ShowsExplorer({ shows, today, sources }: { shows: Show[]; today: string; sources: { host: string; kind: string }[] }) {
  const [city, setCity] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [officialOnly, setOfficialOnly] = useState(false);
  const [withinDays, setWithinDays] = useState<number | null>(null);

  const inScope = useMemo(() => filterShows(shows, { city: null, query, officialOnly, withinDays }, today), [shows, query, officialOnly, withinDays, today]);
  const cities = useMemo(() => cityCounts(inScope), [inScope]);
  const visible = useMemo(() => (city ? inScope.filter((s) => s.city === city) : inScope), [inScope, city]);
  const groups = useMemo(() => groupByDate(visible), [visible]);
  const confirmed = shows.filter((s) => s.confidence === "confirmed").length;

  const chip = (on: boolean) => cn("rounded-full border-2 px-3.5 py-1.5 text-sm font-bold transition-colors", on ? "border-volt bg-volt text-ink" : "border-line text-bone hover:border-mist");

  return (
    <div className="flex flex-col gap-6">
      <p className="max-w-3xl text-mist">
        <b className="text-bone">{shows.length} upcoming shows</b> in {cityCounts(shows).length} cities ({confirmed} confirmed by an official source,
        {" "}{shows.length - confirmed} reported by news and not yet confirmed). This is everything we have found, for any artist, not only the ones you follow.
        It is <b className="text-bone">not</b> every concert in India: we can only list what the pages we are allowed to read publish.
      </p>

      <div className="sticky top-0 z-10 -mx-2 flex flex-col gap-3 rounded-2xl bg-ink/95 px-2 py-3 backdrop-blur">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-52 flex-1">
            <Search aria-hidden className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-mist" />
            <label htmlFor="shows-search" className="sr-only">Search shows</label>
            <input id="shows-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search artist, festival, venue or city…"
              className="w-full rounded-xl border border-line bg-ink-2 py-2.5 pl-9 pr-3 text-bone placeholder:text-mist" />
          </div>
          <button type="button" aria-pressed={officialOnly} onClick={() => setOfficialOnly((v) => !v)} className={chip(officialOnly)}>Official sources only</button>
          <button type="button" aria-pressed={withinDays === 30} onClick={() => setWithinDays((v) => (v === 30 ? null : 30))} className={chip(withinDays === 30)}>Next 30 days</button>
        </div>
        <div role="group" aria-label="City" className="flex flex-wrap gap-1.5">
          <button type="button" aria-pressed={city === null} onClick={() => setCity(null)} className={chip(city === null)}>All cities · {inScope.length}</button>
          {cities.map((c) => (
            <button key={c.city} type="button" aria-pressed={city === c.city} onClick={() => setCity(city === c.city ? null : c.city)} className={chip(city === c.city)}>
              {c.city} · {c.count}
            </button>
          ))}
        </div>
        <p aria-live="polite" className="text-sm text-mist">{visible.length} show{visible.length === 1 ? "" : "s"}</p>
      </div>

      {groups.length === 0 && <p className="rounded-2xl border border-dashed border-line p-6 text-mist">No shows match. Try clearing a filter.</p>}
      <Reveal scroll y={18} stagger={0.04} className="flex flex-col gap-6">
        {groups.map((g) => (
          <section key={g.date ?? "tba"} className="flex flex-col gap-2">
            <h2 className="font-display text-2xl font-extrabold text-volt">{fmtDate(g.date)}</h2>
            <ul className="flex flex-col divide-y divide-line rounded-2xl border border-line bg-ink-2">
              {g.shows.map((s) => (
                <li key={s.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4">
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <Link href={`/events/${s.id}`} className="font-display text-xl font-extrabold hover:text-volt">{s.artist}</Link>
                    {s.name && s.name !== s.artist && <span className="truncate text-sm text-mist">{s.name}</span>}
                    <span className="flex items-center gap-1.5 text-sm text-mist"><MapPin aria-hidden className="size-3.5" />{placeLabel(s.venue, s.city)}</span>
                  </div>
                  <span className={cn("rounded-full px-2.5 py-1 text-xs font-extrabold uppercase", s.confidence === "confirmed" ? "bg-volt text-ink" : "border-2 border-dashed border-acid text-acid")}>{s.confidence}</span>
                  <span className="text-xs text-mist">{s.sourceType ? sourceLabel[s.sourceType] ?? s.sourceType : "Source not recorded"}</span>
                  {s.link ? (
                    <a href={s.link} target="_blank" rel={s.sourceType === "jambase" ? "nofollow noopener noreferrer" : "noopener noreferrer"} className="flex items-center gap-1.5 rounded-full bg-ink-3 px-3.5 py-1.5 text-sm font-bold text-bone hover:bg-line">
                      {bookingLabel(s.confidence)} <ExternalLink aria-hidden className="size-3.5" />
                    </a>
                  ) : <span className="text-xs text-mist">No link published yet</span>}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </Reveal>

      <details className="rounded-2xl border border-line bg-ink-2 p-4">
        <summary className="cursor-pointer font-bold">Where this comes from ({sources.length} sources)</summary>
        <p className="mt-2 text-sm text-mist">Official artist and promoter pages (read politely, robots.txt respected), plus Indian music-news feeds that allow it. We never scrape ticketing sites such as BookMyShow, Insider or District.</p>
        <ul className="mt-3 flex flex-wrap gap-2 text-sm">
          {sources.map((s) => <li key={s.host + s.kind} className="rounded-full border border-line px-3 py-1">{s.host} <span className="text-mist">· {s.kind}</span></li>)}
        </ul>
      </details>
    </div>
  );
}

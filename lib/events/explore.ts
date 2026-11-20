/** Pure helpers for the all-shows page: filter, group, count. */
export type Show = {
  id: string;
  artist: string;
  name: string | null;
  city: string | null;
  venue: string | null;
  date: string | null;               // YYYY-MM-DD or null (date to be announced)
  confidence: "confirmed" | "unconfirmed";
  status: string;
  link: string | null;
  sourceType: string | null;
};

export type Filters = { city: string | null; query: string; officialOnly: boolean; withinDays: number | null };

const norm = (s: string) => s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function filterShows(shows: Show[], f: Filters, today: string): Show[] {
  const limit = f.withinDays === null ? null : new Date(new Date(today + "T00:00:00Z").getTime() + f.withinDays * 86_400_000).toISOString().slice(0, 10);
  const q = norm(f.query).trim();
  return shows.filter((s) =>
    (f.city === null || s.city === f.city) &&
    (!f.officialOnly || s.confidence === "confirmed") &&
    (limit === null || (s.date !== null && s.date <= limit)) &&
    (q === "" || norm([s.artist, s.name ?? "", s.venue ?? "", s.city ?? ""].join(" ")).includes(q)),
  );
}

export function cityCounts(shows: Show[]): { city: string; count: number }[] {
  const m = new Map<string, number>();
  for (const s of shows) if (s.city) m.set(s.city, (m.get(s.city) ?? 0) + 1);
  return [...m.entries()].map(([city, count]) => ({ city, count })).sort((a, b) => b.count - a.count || a.city.localeCompare(b.city));
}

/** Date groups in order; shows with no date go last. */
export function groupByDate(shows: Show[]): { date: string | null; shows: Show[] }[] {
  const m = new Map<string | null, Show[]>();
  for (const s of [...shows].sort((a, b) => (a.date ?? "9999").localeCompare(b.date ?? "9999") || a.artist.localeCompare(b.artist))) {
    m.set(s.date, [...(m.get(s.date) ?? []), s]);
  }
  return [...m.entries()].map(([date, list]) => ({ date, shows: list }));
}

/** "Venue, City" without repeating the city when the venue text already ends with it. */
export function placeLabel(venue: string | null, city: string | null): string {
  if (!venue) return city ?? "City to be announced";
  if (!city) return venue;
  const v = venue.trim().toLowerCase(), c = city.trim().toLowerCase();
  return v.endsWith(c) ? venue : `${venue}, ${city}`;
}

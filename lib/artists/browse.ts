export type BrowseArtist = { artist_id: string; artist_name: string; region: "india" | "world" | null };

/** Letter bucket for A-Z navigation: first letter ignoring accents; digits and symbols go to "#". */
export function letterOf(name: string): string {
  const first = name.normalize("NFKD").replace(/[̀-ͯ]/g, "").trim().charAt(0).toUpperCase();
  return /[A-Z]/.test(first) ? first : "#";
}

export const LETTERS = [..."ABCDEFGHIJKLMNOPQRSTUVWXYZ", "#"] as const;

export function matchesQuery(name: string, query: string): boolean {
  const norm = (s: string) => s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const q = norm(query).trim();
  return q === "" || norm(name).includes(q);
}

export type Region = "all" | "india" | "world";

export function filterArtists(artists: BrowseArtist[], opts: { region: Region; letter: string | null; query: string }): BrowseArtist[] {
  return artists.filter(
    (a) =>
      (opts.region === "all" || a.region === opts.region) &&
      (opts.letter === null || letterOf(a.artist_name) === opts.letter) &&
      matchesQuery(a.artist_name, opts.query),
  );
}

/** Sorted groups for rendering, case/accent-insensitive within a letter. */
export function groupByLetter(artists: BrowseArtist[]): { letter: string; artists: BrowseArtist[] }[] {
  const by = new Map<string, BrowseArtist[]>();
  for (const a of artists) {
    const l = letterOf(a.artist_name);
    by.set(l, [...(by.get(l) ?? []), a]);
  }
  const cmp = (x: BrowseArtist, y: BrowseArtist) => x.artist_name.localeCompare(y.artist_name, "en", { sensitivity: "base" });
  return LETTERS.filter((l) => by.has(l)).map((l) => ({ letter: l, artists: by.get(l)!.sort(cmp) }));
}

export function letterCounts(artists: BrowseArtist[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const a of artists) out[letterOf(a.artist_name)] = (out[letterOf(a.artist_name)] ?? 0) + 1;
  return out;
}

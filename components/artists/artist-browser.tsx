"use client";

import { Check, Plus, Search } from "lucide-react";
import { useMemo, useState, useTransition } from "react";
import { followArtistById, unfollowArtist } from "@/lib/artists/actions";
import { filterArtists, groupByLetter, LETTERS, letterCounts, letterOf, type BrowseArtist, type Region } from "@/lib/artists/browse";
import { cn } from "@/lib/utils/cn";

const regions: { key: Region; label: string }[] = [
  { key: "all", label: "All" },
  { key: "india", label: "India" },
  { key: "world", label: "World" },
];

export function ArtistBrowser({ artists, followedIds }: { artists: BrowseArtist[]; followedIds: string[] }) {
  const [followed, setFollowed] = useState(() => new Set(followedIds));
  const [region, setRegion] = useState<Region>("all");
  const [letter, setLetter] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string>();
  const [, start] = useTransition();

  const inScope = useMemo(() => filterArtists(artists, { region, letter: null, query }), [artists, region, query]);
  const counts = useMemo(() => letterCounts(inScope), [inScope]);
  const groups = useMemo(() => groupByLetter(letter ? inScope.filter((a) => letterOf(a.artist_name) === letter) : inScope), [inScope, letter]);

  function toggle(a: BrowseArtist) {
    const was = followed.has(a.artist_id);
    setError(undefined);
    setFollowed((s) => { const n = new Set(s); if (was) n.delete(a.artist_id); else n.add(a.artist_id); return n; });
    start(async () => {
      const res = was ? await unfollowArtist(a.artist_id) : await followArtistById(a.artist_id);
      if (res.error) {
        setError(res.error);
        setFollowed((s) => { const n = new Set(s); if (was) n.add(a.artist_id); else n.delete(a.artist_id); return n; });   // revert
      }
    });
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="sticky top-0 z-10 -mx-2 flex flex-col gap-3 rounded-2xl bg-ink/95 px-2 py-3 backdrop-blur">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-52 flex-1">
            <Search aria-hidden className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-mist" />
            <label htmlFor="browse-search" className="sr-only">Search artists</label>
            <input id="browse-search" value={query} onChange={(e) => { setQuery(e.target.value); setLetter(null); }} placeholder="Search the catalog…"
              className="w-full rounded-xl border border-line bg-ink-2 py-2.5 pl-9 pr-3 text-bone placeholder:text-mist" />
          </div>
          <div role="group" aria-label="Region" className="flex gap-1 rounded-full border border-line p-1">
            {regions.map((r) => (
              <button key={r.key} type="button" aria-pressed={region === r.key} onClick={() => { setRegion(r.key); setLetter(null); }}
                className={cn("rounded-full px-4 py-1.5 text-sm font-bold", region === r.key ? "bg-volt text-ink" : "text-bone hover:bg-ink-3")}>{r.label}</button>
            ))}
          </div>
        </div>
        <nav aria-label="Jump to letter" className="flex flex-wrap gap-1">
          <button type="button" aria-pressed={letter === null} onClick={() => setLetter(null)}
            className={cn("rounded-md px-2.5 py-1 text-sm font-bold", letter === null ? "bg-acid text-ink" : "text-bone hover:bg-ink-3")}>All</button>
          {LETTERS.map((l) => {
            const n = counts[l] ?? 0;
            return (
              <button key={l} type="button" disabled={n === 0} aria-pressed={letter === l} aria-label={`${l}, ${n} artists`} onClick={() => setLetter(l)}
                className={cn("w-8 rounded-md py-1 text-sm font-bold", letter === l ? "bg-acid text-ink" : n === 0 ? "text-line" : "text-bone hover:bg-ink-3")}>{l}</button>
            );
          })}
        </nav>
        <p aria-live="polite" className="text-sm text-mist">
          {inScope.length} artist{inScope.length === 1 ? "" : "s"}{letter ? ` starting with ${letter}` : ""} · you follow {followed.size}
          <span className="font-semibold text-hotpink">{error ? ` · ${error}` : ""}</span>
        </p>
      </div>

      {groups.length === 0 && (
        <p className="rounded-2xl border border-dashed border-line p-6 text-mist">
          No match in the catalog. You can still follow anyone: go back to Artists, type the name and press Enter.
        </p>
      )}
      {groups.map((g) => (
        <section key={g.letter} aria-labelledby={`l-${g.letter}`} className="flex flex-col gap-2">
          <h2 id={`l-${g.letter}`} className="font-display text-3xl font-extrabold text-volt">{g.letter}</h2>
          <ul className="flex flex-wrap gap-2">
            {g.artists.map((a) => {
              const on = followed.has(a.artist_id);
              return (
                <li key={a.artist_id}>
                  <button type="button" aria-pressed={on} onClick={() => toggle(a)}
                    className={cn("flex items-center gap-1.5 rounded-full border-2 px-3.5 py-1.5 font-bold transition-colors",
                      on ? "border-volt bg-volt text-ink" : "border-line text-bone hover:border-mist")}>
                    {on ? <Check aria-hidden className="size-4" /> : <Plus aria-hidden className="size-4 text-volt" />}{a.artist_name}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

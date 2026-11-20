"use client";

import { Plus, X } from "lucide-react";
import { useEffect, useState, useTransition } from "react";
import { followArtist, searchArtists, unfollowArtist, type Artist } from "@/lib/artists/actions";
import { normalizeArtistName } from "@/lib/artists/validate";

const chipTones = ["bg-volt text-ink", "bg-grape text-bone", "bg-hotpink text-ink", "bg-ember text-ink", "bg-acid text-ink"];

export function ArtistPicker({ followed, suggestions = [] }: { followed: Artist[]; suggestions?: Artist[] }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Artist[]>([]);
  const [error, setError] = useState<string>();
  const [pending, start] = useTransition();
  const [justFollowed, setJustFollowed] = useState<Set<string>>(new Set());

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return; // results are hidden below 2 chars, see render gate
    let cancelled = false;
    const t = setTimeout(async () => { const r = await searchArtists(q); if (!cancelled) setResults(r); }, 250);
    return () => { cancelled = true; clearTimeout(t); };
  }, [query]);

  const followedIds = new Set(followed.map((a) => a.artist_id));
  const name = normalizeArtistName(query);
  const exact = results.some((r) => r.artist_name.toLowerCase() === name.toLowerCase());

  function follow(n: string) {
    setError(undefined);
    start(async () => {
      const res = await followArtist(n);
      if (res.error) setError(res.error); else { setQuery(""); setResults([]); }
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="relative">
        <label htmlFor="artist-search" className="sr-only">Search or add an artist</label>
        <input id="artist-search" value={query} onChange={(e) => setQuery(e.target.value)} autoComplete="off"
          placeholder="Search, or type any artist and press Enter…"
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (name) follow(name); } }}
          className="w-full rounded-xl border border-line bg-ink-2 px-4 py-3 text-bone placeholder:text-mist" />
        {name.length >= 2 && (
          <ul className="mt-2 flex flex-col gap-1 rounded-xl border border-line bg-ink-2 p-2">
            {results.filter((r) => !followedIds.has(r.artist_id)).map((r) => (
              <li key={r.artist_id}>
                <button type="button" disabled={pending} onClick={() => follow(r.artist_name)}
                  className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left hover:bg-ink-3">
                  {r.artist_name}<Plus aria-hidden className="size-4 text-volt" />
                </button>
              </li>
            ))}
            {!exact && (
              <li>
                <button type="button" disabled={pending} onClick={() => follow(name)}
                  className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left font-semibold text-acid hover:bg-ink-3">
                  Add “{name}” as a new artist<Plus aria-hidden className="size-4" />
                </button>
              </li>
            )}
          </ul>
        )}
      </div>
      <p aria-live="polite" className="min-h-5 text-sm font-semibold text-hotpink">{error}</p>
      {suggestions.filter((a) => !followedIds.has(a.artist_id) && !justFollowed.has(a.artist_id)).length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-bold uppercase tracking-wide text-mist">Popular on Live Show Radar: tap to follow</h3>
          <ul className="flex flex-wrap gap-2">
            {suggestions.filter((a) => !followedIds.has(a.artist_id) && !justFollowed.has(a.artist_id)).map((a) => (
              <li key={a.artist_id}>
                <button type="button" disabled={pending}
                  onClick={() => { setJustFollowed((s) => new Set(s).add(a.artist_id)); follow(a.artist_name); }}
                  className="flex items-center gap-1 rounded-full border-2 border-line px-4 py-1.5 font-bold hover:border-volt">
                  <Plus aria-hidden className="size-4 text-volt" />{a.artist_name}
                </button>
              </li>
            ))}
          </ul>
          <p className="text-xs text-mist">These are popular picks, not personalised to your taste yet (we don&apos;t read your listening data).</p>
        </div>
      )}
      {followed.length === 0 ? (
        <p className="text-mist">You&apos;re not following anyone yet.</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {followed.map((a, i) => (
            <li key={a.artist_id} className={`flex items-center gap-1 rounded-full py-1.5 pl-4 pr-2 font-bold ${chipTones[i % chipTones.length]}`}>
              {a.artist_name}
              <button type="button" disabled={pending} aria-label={`Unfollow ${a.artist_name}`}
                onClick={() => start(async () => { const r = await unfollowArtist(a.artist_id); if (r.error) setError(r.error); })}
                className="rounded-full p-1 hover:bg-ink/20"><X aria-hidden className="size-4" /></button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

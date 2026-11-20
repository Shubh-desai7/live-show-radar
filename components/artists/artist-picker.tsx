"use client";

import { Plus, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, useTransition } from "react";
import { SaveBar, useUnsavedWarning } from "@/components/save-bar";
import { saveArtistChanges, searchArtists, type Artist } from "@/lib/artists/actions";
import { dedupeNames } from "@/lib/artists/selection";
import { normalizeArtistName } from "@/lib/artists/validate";

const tones = ["bg-volt text-ink", "bg-grape text-bone", "bg-hotpink text-ink", "bg-ember text-ink", "bg-acid text-ink"];

/** Edit followed artists locally; nothing is written until "Save artists" is pressed. */
export function ArtistPicker({ followed, suggestions = [] }: { followed: Artist[]; suggestions?: Artist[] }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Artist[]>([]);
  const [added, setAdded] = useState<Artist[]>([]);          // existing catalog artists staged for follow
  const [addedNames, setAddedNames] = useState<string[]>([]); // typed names staged (created on save if new)
  const [removed, setRemoved] = useState<Set<string>>(new Set()); // saved artists staged for unfollow
  const [error, setError] = useState<string>();
  const [savedNote, setSavedNote] = useState<string>();
  const [saving, start] = useTransition();

  const savedIds = new Set(followed.map((a) => a.artist_id));
  const stagedIds = new Set(added.map((a) => a.artist_id));
  const changes = added.length + addedNames.length + removed.size;
  useUnsavedWarning(changes > 0);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return; // results are hidden below 2 chars, see render gate
    let cancelled = false;
    const t = setTimeout(async () => { const r = await searchArtists(q); if (!cancelled) setResults(r); }, 250);
    return () => { cancelled = true; clearTimeout(t); };
  }, [query]);

  const name = normalizeArtistName(query);
  const exact = results.some((r) => r.artist_name.toLowerCase() === name.toLowerCase());

  function stage(a: Artist) {
    setSavedNote(undefined);
    if (removed.has(a.artist_id)) { setRemoved((s) => { const n = new Set(s); n.delete(a.artist_id); return n; }); return; }
    if (!savedIds.has(a.artist_id) && !stagedIds.has(a.artist_id)) setAdded((l) => [...l, a]);
    setQuery("");
  }
  function stageName(n: string) {
    setSavedNote(undefined);
    setAddedNames((l) => dedupeNames([...l, n]));
    setQuery("");
  }
  function discard() { setAdded([]); setAddedNames([]); setRemoved(new Set()); setError(undefined); }
  function save() {
    setError(undefined);
    start(async () => {
      const res = await saveArtistChanges({ addIds: added.map((a) => a.artist_id), addNames: addedNames, removeIds: [...removed] });
      if (res.error) { setError(res.error); return; }
      setAdded([]); setAddedNames([]); setRemoved(new Set());
      setSavedNote("Saved. We'll look for their shows on the next check (within about 30 minutes).");
    });
  }

  const visibleSuggestions = suggestions.filter((a) => !savedIds.has(a.artist_id) && !stagedIds.has(a.artist_id));

  return (
    <div className="flex flex-col gap-4">
      <div className="relative">
        <label htmlFor="artist-search" className="sr-only">Search or add an artist</label>
        <input id="artist-search" value={query} onChange={(e) => setQuery(e.target.value)} autoComplete="off"
          placeholder="Search, or type any artist and press Enter…"
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (name) { const m = results.find((r) => r.artist_name.toLowerCase() === name.toLowerCase()); if (m) stage(m); else stageName(name); } } }}
          className="w-full rounded-xl border border-line bg-ink-2 px-4 py-3 text-bone placeholder:text-mist" />
        {name.length >= 2 && (
          <ul className="mt-2 flex flex-col gap-1 rounded-xl border border-line bg-ink-2 p-2">
            {results.filter((r) => !savedIds.has(r.artist_id) && !stagedIds.has(r.artist_id)).map((r) => (
              <li key={r.artist_id}>
                <button type="button" onClick={() => stage(r)} className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left hover:bg-ink-3">
                  {r.artist_name}<Plus aria-hidden className="size-4 text-volt" />
                </button>
              </li>
            ))}
            {!exact && (
              <li>
                <button type="button" onClick={() => stageName(name)}
                  className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left font-semibold text-acid hover:bg-ink-3">
                  Add “{name}” as a new artist<Plus aria-hidden className="size-4" />
                </button>
              </li>
            )}
          </ul>
        )}
      </div>

      {visibleSuggestions.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-bold uppercase tracking-wide text-mist">Popular on Live Show Radar: tap to add</h3>
          <ul className="flex flex-wrap gap-2">
            {visibleSuggestions.map((a) => (
              <li key={a.artist_id}>
                <button type="button" onClick={() => stage(a)}
                  className="flex items-center gap-1 rounded-full border-2 border-line px-4 py-1.5 font-bold hover:border-volt">
                  <Plus aria-hidden className="size-4 text-volt" />{a.artist_name}
                </button>
              </li>
            ))}
          </ul>
          <Link href="/artists/browse" className="w-fit font-bold text-volt underline">Browse all artists A–Z (India and world) →</Link>
          <p className="text-xs text-mist">Popular picks, not personalised to your taste yet. Nothing is saved until you press Save.</p>
        </div>
      )}

      {followed.length + added.length + addedNames.length === 0 ? (
        <p className="text-mist">You&apos;re not following anyone yet.</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {followed.map((a, i) => {
            const off = removed.has(a.artist_id);
            return (
              <li key={a.artist_id} className={`flex items-center gap-1 rounded-full py-1.5 pl-4 pr-2 font-bold ${off ? "border-2 border-dashed border-hotpink text-mist line-through" : tones[i % tones.length]}`}>
                {a.artist_name}
                <button type="button" aria-label={off ? `Keep ${a.artist_name}` : `Unfollow ${a.artist_name}`}
                  onClick={() => { setSavedNote(undefined); setRemoved((s) => { const n = new Set(s); if (off) n.delete(a.artist_id); else n.add(a.artist_id); return n; }); }}
                  className="rounded-full p-1 hover:bg-ink/20">{off ? <Plus aria-hidden className="size-4" /> : <X aria-hidden className="size-4" />}</button>
              </li>
            );
          })}
          {added.map((a) => (
            <li key={a.artist_id} className="flex items-center gap-1 rounded-full border-2 border-dashed border-acid py-1.5 pl-4 pr-2 font-bold text-acid">
              {a.artist_name} <span className="text-xs uppercase">unsaved</span>
              <button type="button" aria-label={`Remove ${a.artist_name} from unsaved`} onClick={() => setAdded((l) => l.filter((x) => x.artist_id !== a.artist_id))} className="rounded-full p-1 hover:bg-ink/20"><X aria-hidden className="size-4" /></button>
            </li>
          ))}
          {addedNames.map((n) => (
            <li key={n} className="flex items-center gap-1 rounded-full border-2 border-dashed border-acid py-1.5 pl-4 pr-2 font-bold text-acid">
              {n} <span className="text-xs uppercase">new, unsaved</span>
              <button type="button" aria-label={`Remove ${n} from unsaved`} onClick={() => setAddedNames((l) => l.filter((x) => x !== n))} className="rounded-full p-1 hover:bg-ink/20"><X aria-hidden className="size-4" /></button>
            </li>
          ))}
        </ul>
      )}

      <SaveBar changes={changes} saving={saving} onSave={save} onDiscard={discard} label="Save artists" savedNote={savedNote} error={error} />
    </div>
  );
}

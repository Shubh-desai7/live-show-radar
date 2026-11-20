import { Suspense } from "react";
import { AppShell, Section } from "@/components/app-shell";
import { ArtistPicker } from "@/components/artists/artist-picker";
import { requireUser } from "@/lib/auth/session";
import { coverageFor } from "@/lib/artists/coverage";
import { loadUserSetup } from "@/lib/settings/queries";

async function Body() {
  const { supabase, user } = await requireUser();
  const { followed, suggestions } = await loadUserSetup(supabase, user.id);
  const ids = followed.map((a) => a.artist_id);
  const [{ data: details }, { data: srcRows }] = ids.length
    ? await Promise.all([
        supabase.from("artists").select("artist_id, official_website, metadata").in("artist_id", ids),
        supabase.from("sources").select("artist_id").in("artist_id", ids),
      ])
    : [{ data: [] }, { data: [] }];
  const counts = new Map<string, number>();
  for (const r of srcRows ?? []) counts.set(r.artist_id as string, (counts.get(r.artist_id as string) ?? 0) + 1);
  const detail = new Map((details ?? []).map((d) => [d.artist_id as string, d]));
  const tone = { good: "text-volt", warn: "text-ember", bad: "text-hotpink", idle: "text-mist" } as const;

  return (
    <>
      <Section title="Artists you follow" hint="Add or remove artists, then press Save.">
        <ArtistPicker followed={followed} suggestions={suggestions} />
      </Section>
      {followed.length > 0 && (
        <Section title="How we watch your artists" hint="A show can only appear if we can read a page that lists it. This is why some artists show nothing.">
          <ul className="flex flex-col divide-y divide-line">
            {followed.map((a) => {
              const d = detail.get(a.artist_id);
              const c = coverageFor({ official_website: (d?.official_website as string | null) ?? null, metadata: (d?.metadata as Record<string, unknown> | null) ?? null }, counts.get(a.artist_id) ?? 0);
              return (
                <li key={a.artist_id} className="flex flex-col gap-0.5 py-3">
                  <span className="flex flex-wrap items-baseline gap-x-3"><b>{a.artist_name}</b><span className={`text-sm font-bold ${tone[c.tone]}`}>{c.label}</span></span>
                  <span className="text-sm text-mist">{c.detail}</span>
                </li>
              );
            })}
          </ul>
          <p className="text-xs text-mist">We also catch artists on promoter pages we check (for example Sunburn), even without their own site.</p>
        </Section>
      )}
    </>
  );
}

export default function ArtistsPage() {
  return (
    <AppShell title="Artists">
      <Suspense fallback={<p className="text-mist">Loading…</p>}><Body /></Suspense>
    </AppShell>
  );
}

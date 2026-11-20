import { Suspense } from "react";
import { AppShell, Section } from "@/components/app-shell";
import { ArtistPicker } from "@/components/artists/artist-picker";
import { requireUser } from "@/lib/auth/session";
import { loadUserSetup } from "@/lib/settings/queries";

async function Body() {
  const { supabase, user } = await requireUser();
  const { followed, suggestions } = await loadUserSetup(supabase, user.id);
  return (
    <Section title="Artists you follow" hint="Add or remove artists any time.">
      <ArtistPicker followed={followed} suggestions={suggestions} />
    </Section>
  );
}

export default function ArtistsPage() {
  return (
    <AppShell title="Artists">
      <Suspense fallback={<p className="text-mist">Loading…</p>}><Body /></Suspense>
    </AppShell>
  );
}

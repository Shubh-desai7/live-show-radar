import Link from "next/link";
import { Suspense } from "react";
import { Section } from "@/components/app-shell";
import { ArtistPicker } from "@/components/artists/artist-picker";
import { CityPicker } from "@/components/settings/city-picker";
import { PreferencesForm } from "@/components/settings/preferences-form";
import { requireUser } from "@/lib/auth/session";
import { isOnboarded } from "@/lib/artists/validate";
import { loadUserSetup } from "@/lib/settings/queries";

async function Body() {
  const { supabase, user } = await requireUser();
  const { followed, cities, prefs } = await loadUserSetup(supabase, user.id);
  const ready = isOnboarded(followed.length, cities.length);
  return (
    <>
      <Section title="1. Who do you want to catch live?" hint="Search, or type any name to add it. Follow as many as you like.">
        <ArtistPicker followed={followed} />
      </Section>
      <Section title="2. Which cities?" hint="Bengaluru first, but pick every city you'd travel to.">
        <CityPicker selected={cities} />
      </Section>
      <Section title="3. What should we alert you about?">
        <PreferencesForm prefs={prefs} />
      </Section>
      {ready ? (
        <Link href="/dashboard" className="w-fit rounded-full bg-volt px-8 py-4 text-lg font-extrabold text-ink">Take me to my radar</Link>
      ) : (
        <p className="text-mist">Follow at least one artist and pick at least one city to continue.</p>
      )}
    </>
  );
}

export default function OnboardingPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col gap-6 px-5 py-10 md:px-8">
      <h1 className="font-display text-6xl font-extrabold leading-[0.9] tracking-tighter">
        Tune your <span className="text-volt">radar</span>.
      </h1>
      <Suspense fallback={<p className="text-mist">Loading…</p>}><Body /></Suspense>
    </main>
  );
}

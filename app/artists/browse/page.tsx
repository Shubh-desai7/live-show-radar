import Link from "next/link";
import { Suspense } from "react";
import { AppShell } from "@/components/app-shell";
import { ArtistBrowser } from "@/components/artists/artist-browser";
import { requireUser } from "@/lib/auth/session";
import type { BrowseArtist } from "@/lib/artists/browse";

async function Body() {
  const { supabase, user } = await requireUser();
  const [catalog, mine] = await Promise.all([
    supabase.from("artists").select("artist_id, artist_name, region").eq("featured", true).order("artist_name").limit(1000),
    supabase.from("user_artists").select("artist_id").eq("user_id", user.id),
  ]);
  return (
    <>
      <p className="max-w-2xl text-mist">
        A curated starter catalog of well-known artists in India and around the world, A to Z. Tap a name to follow or unfollow.
        Not listed? <Link href="/artists" className="font-bold text-volt underline">Type any artist</Link> and we&apos;ll add them.
      </p>
      <ArtistBrowser artists={(catalog.data ?? []) as BrowseArtist[]} followedIds={(mine.data ?? []).map((r) => r.artist_id as string)} />
    </>
  );
}

export default function BrowsePage() {
  return (
    <AppShell title="All artists">
      <Suspense fallback={<p className="text-mist">Loading…</p>}><Body /></Suspense>
    </AppShell>
  );
}

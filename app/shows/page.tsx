import { Suspense } from "react";
import { AppShell } from "@/components/app-shell";
import { ShowsExplorer } from "@/components/events/shows-explorer";
import { requireUser } from "@/lib/auth/session";
import type { Show } from "@/lib/events/explore";
import { loadAllUpcoming } from "@/lib/events/queries";
import { toVisible } from "@/lib/events/status";

const kind: Record<string, string> = { artist_website: "artist site", promoter_website: "promoter", publisher_rss: "news feed", google_news_rss: "news", newsletter: "newsletter" };

async function Body() {
  const { supabase } = await requireUser();
  const now = new Date();
  const [events, { data: sourceRows }] = await Promise.all([
    loadAllUpcoming(supabase, now),
    supabase.from("sources").select("source_type, source_url").in("source_type", ["artist_website", "promoter_website", "publisher_rss"]),
  ]);
  const shows: Show[] = events.flatMap((e) => {
    const confidence = toVisible(e.confidence);
    if (!confidence) return [];
    return [{ id: e.event_id, artist: e.artist.artist_name, name: e.event_name, city: e.city, venue: e.venue, date: e.event_date, confidence,
      status: e.status, link: e.tickets?.booking_url ?? e.booking_url, sourceType: e.source?.source_type ?? null }];
  });
  const seen = new Set<string>();
  const sources = (sourceRows ?? []).flatMap((r) => {
    try {
      const host = new URL(r.source_url as string).hostname.replace(/^www\./, "");
      const k = kind[r.source_type as string] ?? "source";
      if (r.source_type === "article" || seen.has(host + k)) return [];
      seen.add(host + k);
      return [{ host, kind: k }];
    } catch { return []; }
  });
  return <ShowsExplorer shows={shows} today={now.toISOString().slice(0, 10)} sources={sources.slice(0, 80)} />;
}

export default function ShowsPage() {
  return (
    <AppShell title="All shows">
      <Suspense fallback={<p className="text-mist">Loading…</p>}><Body /></Suspense>
    </AppShell>
  );
}

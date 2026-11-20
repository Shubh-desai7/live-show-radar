import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { AppShell, Section } from "@/components/app-shell";
import { EventCard } from "@/components/events/event-card";
import { requireUser } from "@/lib/auth/session";
import { isOnboarded } from "@/lib/artists/validate";
import { deadlineLabel, formatMoment, isNewlyAnnounced, timeUntil, upcomingDeadlines } from "@/lib/events/dashboard";
import { loadEventsForUser } from "@/lib/events/queries";
import { loadUserSetup } from "@/lib/settings/queries";

async function Body() {
  const { supabase, user } = await requireUser();
  const { followed, cities, timezone } = await loadUserSetup(supabase, user.id);
  if (!isOnboarded(followed.length, cities.length)) redirect("/onboarding");

  const now = new Date();
  const [{ data: sourceRows }, { data: officialRows }] = await Promise.all([
    supabase.from("sources").select("source_type, source_url"),
    supabase.from("artists").select("artist_id").in("artist_id", followed.map((a) => a.artist_id)).not("official_website", "is", null),
  ]);
  const hosts = [...new Set((sourceRows ?? []).map((r) => { try { return new URL(r.source_url as string).hostname.replace(/^www\./, ""); } catch { return null; } }).filter((h): h is string => !!h))];
  const withOwnPage = officialRows?.length ?? 0;
  const events = (await loadEventsForUser(supabase, followed.map((a) => a.artist_id), cities, now))
    .sort((a, b) => (a.event_date ?? "9999").localeCompare(b.event_date ?? "9999"));
  const active = events.filter((e) => e.status !== "cancelled" && e.status !== "completed");

  const deadlines = active
    .flatMap((e) => upcomingDeadlines(e.tickets, now).map((d) => ({ e, ...d })))
    .sort((a, b) => a.at.getTime() - b.at.getTime())
    .slice(0, 6);
  const fresh = active.filter((e) => isNewlyAnnounced(e.first_seen_at, now));

  return (
    <>
      <p className="text-mist">
        Watching {followed.length} artist{followed.length === 1 ? "" : "s"} in {cities.join(", ")}.{" "}
        <Link href="/artists" className="font-bold text-volt underline">Manage</Link>
      </p>

      {events.length === 0 ? (
        <Section title="Upcoming shows">
          {/* Honest empty state: no fake events. Discovery arrives in steps 6-8. */}
          <div className="rounded-2xl border border-dashed border-line p-8 text-mist">
            No shows found yet for your artists in your cities. That does not mean none are happening: we only check a few sources so far (see &ldquo;How we find your shows&rdquo; below).
          </div>
        </Section>
      ) : (
        <>
          {deadlines.length > 0 && (
            <Section title="Don't miss these" hint={`Times shown in ${timezone}.`}>
              <ul className="flex flex-col gap-3">
                {deadlines.map(({ e, kind, at }) => (
                  <li key={`${e.event_id}-${kind}`}>
                    <Link href={`/events/${e.event_id}`} className="flex flex-wrap items-center gap-3 rounded-2xl bg-ink-3 p-4 hover:bg-line">
                      <span className="rounded-md bg-acid px-2 py-1 text-xs font-extrabold uppercase text-ink">{timeUntil(at, now)}</span>
                      <span className="font-display text-xl font-extrabold">{e.artist.artist_name}</span>
                      <span className="text-mist">{deadlineLabel[kind]}: {formatMoment(at, timezone, !!e.tickets?.timing_reliable)}</span>
                      {!e.tickets?.timing_reliable && <span className="text-xs font-bold text-ember">timing not verified</span>}
                    </Link>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {fresh.length > 0 && (
            <Section title="Just announced" hint="First spotted in the last 7 days.">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {fresh.map((e) => <EventCard key={e.event_id} event={e} now={now} />)}
              </div>
            </Section>
          )}

          <Section title="All upcoming shows">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {events.map((e) => <EventCard key={e.event_id} event={e} now={now} />)}
            </div>
          </Section>
        </>
      )}
      <Section title="How we find your shows">
        <p className="text-mist">
          We check {hosts.length} source{hosts.length === 1 ? "" : "s"} a few times a day{hosts.length ? <>: <b className="text-bone">{hosts.join(", ")}</b></> : null}.
          A show appears here only if one of those pages lists one of your {followed.length} artists in one of your {cities.length} cities.
          {" "}{withOwnPage} of your artists {withOwnPage === 1 ? "has" : "have"} their own official page being checked; for the rest we depend on promoter pages.
        </p>
        <p className="text-sm text-mist">
          So an empty list means &ldquo;none found in the pages we can read&rdquo;, not &ldquo;no shows&rdquo;. We don&apos;t scrape ticketing sites like BookMyShow or Insider, and many artist sites can&apos;t be read automatically. Adding more sources is how coverage grows.
        </p>
      </Section>
    </>
  );
}

export default function DashboardPage() {
  return (
    <AppShell title="Your radar">
      <Suspense fallback={<p className="text-mist">Loading…</p>}><Body /></Suspense>
    </AppShell>
  );
}

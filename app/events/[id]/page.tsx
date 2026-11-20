import { ExternalLink } from "lucide-react";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { AppShell, Section } from "@/components/app-shell";
import { VerificationBadge } from "@/components/events/verification-badge";
import { requireUser } from "@/lib/auth/session";
import { deadlineLabel, formatDateTime, formatEventDate, formatMoment, sourceTypeLabel, upcomingDeadlines, type DeadlineKind } from "@/lib/events/dashboard";
import { loadEvent } from "@/lib/events/queries";
import { toVisible } from "@/lib/events/status";
import { loadUserSetup } from "@/lib/settings/queries";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const earlyBird = { available: "Early-bird tickets available", ended: "Early-bird has ended", not_offered: "No early-bird tier", unknown: "Early-bird status unknown" } as const;
const explain = {
  confirmed: "Confirmed by an official artist, promoter or ticketing source.",
  unconfirmed: "Reported by a credible secondary source and not yet officially confirmed. Details may change.",
} as const;

async function Body({ id }: { id: string }) {
  if (!UUID.test(id)) notFound();
  const { supabase, user } = await requireUser();
  const [event, { timezone }] = await Promise.all([loadEvent(supabase, id), loadUserSetup(supabase, user.id)]);
  if (!event) notFound(); // also the result for rumoured events: RLS hides them
  const confidence = toVisible(event.confidence)!;
  const t = event.tickets;
  const link = t?.booking_url ?? event.booking_url;
  const now = new Date();
  const future = new Set(upcomingDeadlines(t, now).map((d) => d.kind));

  const rows: [DeadlineKind, string | null | undefined][] = [
    ["presale_registration", t?.presale_registration_deadline],
    ["presale_opening", t?.presale_opening],
    ["general_sale", t?.general_sale_opening],
  ];

  return (
    <>
      <p className="font-display text-4xl font-extrabold tracking-tight md:text-6xl">{event.artist.artist_name}</p>
      <div className="flex flex-wrap items-center gap-3">
        <VerificationBadge confidence={confidence} />
        {event.status !== "scheduled" && <span className="rounded-md bg-hotpink px-2 py-1 text-xs font-extrabold uppercase text-ink">{event.status}</span>}
      </div>
      <p className="max-w-2xl text-lg text-mist">{explain[confidence]}</p>

      <Section title="The show">
        <dl className="grid gap-3 sm:grid-cols-3">
          <div><dt className="text-sm text-mist">Where</dt><dd className="font-bold">{event.venue ? `${event.venue}, ` : ""}{event.city ?? "City to be announced"}</dd></div>
          <div><dt className="text-sm text-mist">When</dt><dd className="font-bold">{formatEventDate(event.event_date)}</dd></div>
          <div><dt className="text-sm text-mist">Event</dt><dd className="font-bold">{event.event_name ?? event.artist.artist_name}</dd></div>
        </dl>
      </Section>

      <Section title="Tickets" hint={`Times shown in ${timezone}.`}>
        {rows.some(([, v]) => v) ? (
          <ul className="flex flex-col gap-2">
            {rows.filter(([, v]) => v).map(([kind, v]) => (
              <li key={kind} className="flex flex-wrap items-baseline gap-2">
                <span className="font-bold">{deadlineLabel[kind]}:</span>
                <span>{formatMoment(v!, timezone, !!t?.timing_reliable)}</span>
                {!future.has(kind) && <span className="text-sm text-mist">(passed)</span>}
              </li>
            ))}
          </ul>
        ) : <p className="text-mist">No ticket dates announced yet.</p>}
        {t && !t.timing_reliable && rows.some(([, v]) => v) && (
          <p className="text-sm font-semibold text-ember">These dates or times aren&apos;t verified, so we won&apos;t send reminders for them. Check the official page.</p>
        )}
        <p className="text-sm text-mist">{earlyBird[t?.early_bird_status ?? "unknown"]}</p>
        {link && (
          <a href={link} target="_blank" rel="noopener noreferrer" className="flex w-fit items-center gap-2 rounded-full bg-volt px-6 py-3 font-extrabold text-ink">
            Book on the official site <ExternalLink aria-hidden className="size-4" />
          </a>
        )}
        <p className="text-sm text-mist">Live Show Radar doesn&apos;t sell tickets. You&apos;ll complete your purchase on the ticketing site.</p>
      </Section>

      <Section title="Where we found this">
        {event.source ? (
          <p>
            {sourceTypeLabel[event.source.source_type] ?? event.source.source_type}:{" "}
            <a href={event.source.source_url} target="_blank" rel="noopener noreferrer" className="break-all font-bold text-volt underline">{event.source.source_url}</a>
          </p>
        ) : <p className="text-mist">Source not recorded.</p>}
        <p className="text-sm text-mist">
          {event.source_published_at && <>Published {formatDateTime(event.source_published_at, timezone)}. </>}
          First seen {formatDateTime(event.first_seen_at, timezone)}.
          {event.last_verified_at && <> Last verified {formatDateTime(event.last_verified_at, timezone)}.</>}
        </p>
      </Section>
    </>
  );
}

async function Page({ params }: PageProps<"/events/[id]">) {
  const { id } = await params;
  return <Body id={id} />;
}

export default function EventPage(props: PageProps<"/events/[id]">) {
  return (
    <AppShell title="Show details">
      <Suspense fallback={<p className="text-mist">Loading…</p>}><Page {...props} /></Suspense>
    </AppShell>
  );
}

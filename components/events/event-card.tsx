import Link from "next/link";
import { ConcertCard } from "./concert-card";
import { deadlineShort, formatEventDate, nextDeadline, timeUntil } from "@/lib/events/dashboard";
import type { EventRow } from "@/lib/events/queries";
import { toVisible } from "@/lib/events/status";

const tones = ["volt", "grape", "hotpink", "ember"] as const;
const toneFor = (name: string) => tones[[...name].reduce((n, c) => n + c.charCodeAt(0), 0) % tones.length];

export function EventCard({ event, now }: { event: EventRow; now: Date }) {
  const confidence = toVisible(event.confidence);
  if (!confidence) return null; // rumoured events are never rendered

  const off = event.status === "cancelled" || event.status === "postponed";
  const next = event.tickets?.timing_reliable ? nextDeadline(event.tickets, now) : null;
  const highlight = off
    ? event.status === "cancelled" ? "Cancelled" : "Postponed"
    : next ? `${deadlineShort[next.kind]} ${timeUntil(next.at, now)}` : undefined;

  return (
    <Link href={`/events/${event.event_id}`} className="block rounded-3xl transition-transform hover:-translate-y-1">
      <ConcertCard
        artist={event.artist.artist_name}
        city={event.city ?? "City TBA"}
        venue={event.venue ?? undefined}
        date={formatEventDate(event.event_date)}
        confidence={confidence}
        highlight={highlight}
        tone={toneFor(event.artist.artist_name)}
        className={off ? "grayscale opacity-70" : undefined}
      />
    </Link>
  );
}

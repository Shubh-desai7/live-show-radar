import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { Tilt } from "@/components/motion/tilt";
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

  const link = event.tickets?.booking_url ?? event.booking_url;

  return (
    <div className="flex flex-col gap-2">
      <Tilt><Link href={`/events/${event.event_id}`} className="block rounded-3xl">
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
      </Link></Tilt>
      {!off && (link ? (
        <a href={link} target="_blank" rel="noopener noreferrer"
          className="flex w-fit items-center gap-1.5 rounded-full bg-volt px-4 py-1.5 text-sm font-extrabold text-ink">
          Official booking link <ExternalLink aria-hidden className="size-3.5" />
        </a>
      ) : (
        <span className="text-sm text-mist">No booking link published yet</span>
      ))}
    </div>
  );
}

import { CalendarDays, MapPin } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import type { Confidence } from "@/lib/events/status";
import { VerificationBadge } from "./verification-badge";

export type ConcertCardProps = {
  artist: string;
  city: string;
  venue?: string;
  date: string;
  confidence: Exclude<Confidence, "rumoured">;
  highlight?: string; // e.g. "Presale opens in 2h"
  tone?: "volt" | "grape" | "hotpink" | "ember";
  className?: string;
};

const tones = {
  volt: "from-volt to-acid text-ink",
  grape: "from-grape to-hotpink text-bone",
  hotpink: "from-hotpink to-ember text-ink",
  ember: "from-ember to-acid text-ink",
} as const;

export function ConcertCard({ artist, city, venue, date, confidence, highlight, tone = "volt", className }: ConcertCardProps) {
  return (
    <article className={cn("relative overflow-hidden rounded-3xl bg-gradient-to-br p-6", tones[tone], className)}>
      <div aria-hidden className="halftone absolute -right-10 -top-10 size-48 rounded-full opacity-25" />
      <div className="relative flex flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <VerificationBadge confidence={confidence} />
          {highlight && (
            <span className="rotate-3 rounded-md bg-ink px-2 py-1 text-xs font-extrabold uppercase text-acid">{highlight}</span>
          )}
        </div>
        <h3 className="font-display text-4xl font-extrabold leading-none tracking-tight">{artist}</h3>
        <dl className="flex flex-col gap-1 text-sm font-semibold">
          <div className="flex items-center gap-2"><MapPin aria-hidden className="size-4" /><dt className="sr-only">Where</dt><dd>{venue ? `${venue}, ${city}` : city}</dd></div>
          <div className="flex items-center gap-2"><CalendarDays aria-hidden className="size-4" /><dt className="sr-only">When</dt><dd>{date}</dd></div>
        </dl>
      </div>
    </article>
  );
}

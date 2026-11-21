/** Pure presentation logic for events and ticket deadlines. All times are UTC ISO strings in, user-timezone text out. */

export type TicketInfo = {
  presale_registration_deadline: string | null;
  presale_opening: string | null;
  general_sale_opening: string | null;
  early_bird_status: "unknown" | "available" | "ended" | "not_offered";
  booking_url: string | null;
  timing_reliable: boolean;
};

export type DeadlineKind = "presale_registration" | "presale_opening" | "general_sale";

export const deadlineLabel: Record<DeadlineKind, string> = {
  presale_registration: "Presale registration closes",
  presale_opening: "Presale opens",
  general_sale: "General sale opens",
};

export const deadlineShort: Record<DeadlineKind, string> = {
  presale_registration: "Register for presale",
  presale_opening: "Presale opens",
  general_sale: "Sale opens",
};

/** Future ticket moments, soonest first. */
export function upcomingDeadlines(t: TicketInfo | null, now: Date): { kind: DeadlineKind; at: Date }[] {
  if (!t) return [];
  const all: [DeadlineKind, string | null][] = [
    ["presale_registration", t.presale_registration_deadline],
    ["presale_opening", t.presale_opening],
    ["general_sale", t.general_sale_opening],
  ];
  return all
    .filter((d): d is [DeadlineKind, string] => !!d[1])
    .map(([kind, iso]) => ({ kind, at: new Date(iso) }))
    .filter((d) => !Number.isNaN(d.at.getTime()) && d.at.getTime() > now.getTime())
    .sort((a, b) => a.at.getTime() - b.at.getTime());
}

export function nextDeadline(t: TicketInfo | null, now: Date) {
  return upcomingDeadlines(t, now)[0] ?? null;
}

export function isNewlyAnnounced(firstSeenIso: string, now: Date, days = 7): boolean {
  const seen = new Date(firstSeenIso).getTime();
  return !Number.isNaN(seen) && now.getTime() - seen >= 0 && now.getTime() - seen < days * 86_400_000;
}

/** "in 2h", "in 3 days", "in 12 min". */
export function timeUntil(at: Date, now: Date): string {
  const mins = Math.round((at.getTime() - now.getTime()) / 60_000);
  if (mins < 60) return `in ${Math.max(mins, 1)} min`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `in ${hours}h`;
  return `in ${Math.round(hours / 24)} days`;
}

export function formatDateTime(iso: string | Date, timeZone: string): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  try {
    return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone }).format(d);
  } catch {
    return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }).format(d);
  }
}

/** Ticket moments: full local time only when the timing is verified. Otherwise the calendar date in IST
 *  (unverified moments are stored as 00:00 IST, so showing a clock time or shifting zones would mislead). */
export function formatMoment(iso: string | Date, timeZone: string, timingReliable: boolean): string {
  if (timingReliable) return formatDateTime(iso, timeZone);
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeZone: "Asia/Kolkata" }).format(d) + " (time not confirmed)";
}

/** event_date is a calendar date (YYYY-MM-DD): format without any timezone shift. */
export function formatEventDate(date: string | null): string {
  if (!date) return "Date to be announced";
  const d = new Date(date + "T00:00:00Z");
  if (Number.isNaN(d.getTime())) return "Date to be announced";
  return new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(d);
}

export function cityMatches(eventCity: string | null, cities: string[]): boolean {
  if (!eventCity) return false;
  const c = eventCity.trim().toLowerCase();
  return cities.some((x) => x.toLowerCase() === c);
}

/** Upcoming = date unknown or today/later (comparison on calendar dates, UTC). */
export function isUpcoming(eventDate: string | null, now: Date): boolean {
  if (!eventDate) return true;
  return eventDate >= now.toISOString().slice(0, 10);
}

export const sourceTypeLabel: Record<string, string> = {
  artist_website: "Official artist website",
  promoter_website: "Promoter website",
  google_news_rss: "News report (Google News)",
  publisher_rss: "News report (publisher feed, not an official source)",
  newsletter: "Newsletter",
  jambase: "Concert database (JamBase, not an official source)",
};

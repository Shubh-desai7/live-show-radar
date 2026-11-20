import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import { cityMatches, isUpcoming, type TicketInfo } from "./dashboard";
import { isUserVisible, type Confidence } from "./status";

export type EventRow = {
  event_id: string;
  event_name: string | null;
  city: string | null;
  venue: string | null;
  event_date: string | null;
  confidence: Confidence;
  status: "scheduled" | "postponed" | "cancelled" | "completed";
  booking_url: string | null;
  source_published_at: string | null;
  first_seen_at: string;
  last_verified_at: string | null;
  artist: { artist_id: string; artist_name: string };
  tickets: TicketInfo | null;
  source: { source_type: string; source_url: string } | null;
};

const SELECT = `event_id, event_name, city, venue, event_date, confidence, status, booking_url,
  source_published_at, first_seen_at, last_verified_at,
  artists(artist_id, artist_name),
  tickets(presale_registration_deadline, presale_opening, general_sale_opening, early_bird_status, booking_url, timing_reliable),
  sources(source_type, source_url)`;

const one = <T,>(v: T | T[] | null | undefined): T | null => (Array.isArray(v) ? (v[0] ?? null) : (v ?? null));

type Raw = Omit<EventRow, "artist" | "tickets" | "source"> & {
  artists: EventRow["artist"] | EventRow["artist"][] | null;
  tickets: TicketInfo | TicketInfo[] | null;
  sources: EventRow["source"] | EventRow["source"][] | null;
};

function normalise(r: Raw): EventRow | null {
  const artist = one(r.artists);
  if (!artist) return null;
  const { artists: _a, tickets, sources, ...rest } = r;
  void _a;
  return { ...rest, artist, tickets: one(tickets), source: one(sources) };
}

/** Upcoming events for the user's followed artists in their cities. RLS already hides rumoured events; we filter again defensively. */
export async function loadEventsForUser(
  supabase: SupabaseClient, followedArtistIds: string[], cities: string[], now: Date,
): Promise<EventRow[]> {
  if (followedArtistIds.length === 0 || cities.length === 0) return [];
  const { data } = await supabase.from("events").select(SELECT).in("artist_id", followedArtistIds).limit(300);
  return ((data ?? []) as unknown as Raw[])
    .map(normalise)
    .filter((e): e is EventRow => !!e)
    .filter((e) => isUserVisible(e.confidence) && cityMatches(e.city, cities) && isUpcoming(e.event_date, now));
}

export async function loadEvent(supabase: SupabaseClient, eventId: string): Promise<EventRow | null> {
  const { data } = await supabase.from("events").select(SELECT).eq("event_id", eventId).maybeSingle();
  const e = data ? normalise(data as unknown as Raw) : null;
  return e && isUserVisible(e.confidence) ? e : null;
}

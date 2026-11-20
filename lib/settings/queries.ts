import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Artist } from "@/lib/artists/actions";

export type Prefs = {
  new_event_alerts: boolean; presale_alerts: boolean; ticket_sale_alerts: boolean; event_update_alerts: boolean;
};

export async function loadUserSetup(supabase: SupabaseClient, userId: string) {
  const [artists, cities, prefs, profile] = await Promise.all([
    supabase.from("user_artists").select("artists(artist_id, artist_name)").eq("user_id", userId).order("created_at"),
    supabase.from("user_cities").select("city").eq("user_id", userId).order("city"),
    supabase.from("notification_preferences")
      .select("new_event_alerts, presale_alerts, ticket_sale_alerts, event_update_alerts")
      .eq("user_id", userId).maybeSingle(),
    supabase.from("profiles").select("timezone, telegram_chat_id").eq("user_id", userId).maybeSingle(),
  ]);
  const followed = ((artists.data ?? []) as unknown as { artists: Artist | null }[])
    .map((r) => r.artists).filter((a): a is Artist => !!a);
  return {
    followed,
    timezone: (profile.data?.timezone as string | undefined) ?? "Asia/Kolkata",
    telegramLinked: profile.data?.telegram_chat_id != null,   // the chat id itself never leaves the server
    cities: (cities.data ?? []).map((c) => c.city as string),
    prefs: (prefs.data as Prefs | null) ?? { new_event_alerts: true, presale_alerts: true, ticket_sale_alerts: true, event_update_alerts: true },
  };
}

"use server";

import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth/session";
import { isKnownCity } from "@/lib/cities";

export type SettingsState = { error?: string; message?: string };

export async function toggleCity(city: string, selected: boolean): Promise<{ error?: string }> {
  if (!isKnownCity(city)) return { error: "Unknown city." };
  const { supabase, user } = await requireUser();
  const { error } = selected
    ? await supabase.from("user_cities").insert({ user_id: user.id, city, country: "India" })
    : await supabase.from("user_cities").delete().eq("user_id", user.id).eq("city", city).eq("country", "India");
  if (error && error.code !== "23505") return { error: "Couldn't update cities. Try again." };
  revalidatePath("/", "layout");
  return {};
}

export async function savePreferences(_: SettingsState, formData: FormData): Promise<SettingsState> {
  const { supabase, user } = await requireUser();
  const on = (k: string) => formData.get(k) === "on";
  const { error } = await supabase
    .from("notification_preferences")
    .update({
      new_event_alerts: on("new_event_alerts"),
      presale_alerts: on("presale_alerts"),
      ticket_sale_alerts: on("ticket_sale_alerts"),
      event_update_alerts: on("event_update_alerts"),
    })
    .eq("user_id", user.id);
  if (error) return { error: "Couldn't save preferences. Try again." };
  revalidatePath("/", "layout");
  return { message: "Saved." };
}


/** Replace the user's tracked cities with exactly this list (validated against the supported cities). */
export async function saveCities(cities: string[]): Promise<{ error?: string }> {
  const wanted = [...new Set(cities)];
  if (wanted.some((c) => !isKnownCity(c))) return { error: "Unknown city." };
  const { supabase, user } = await requireUser();
  if (wanted.length) {
    const { error } = await supabase.from("user_cities")
      .upsert(wanted.map((city) => ({ user_id: user.id, city, country: "India" })), { onConflict: "user_id,city,country", ignoreDuplicates: true });
    if (error) return { error: "Couldn't save your cities. Try again." };
  }
  let del = supabase.from("user_cities").delete().eq("user_id", user.id);
  if (wanted.length) del = del.not("city", "in", `(${wanted.map((c) => `"${c}"`).join(",")})`);
  const { error } = await del;
  if (error) return { error: "Couldn't update your cities. Try again." };
  revalidatePath("/", "layout");
  return {};
}

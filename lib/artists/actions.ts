"use server";

import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth/session";
import { escapeLike, validateArtistName } from "./validate";

export type Artist = { artist_id: string; artist_name: string };
export type ActionResult = { error?: string };

export async function searchArtists(query: string): Promise<Artist[]> {
  const { supabase } = await requireUser();
  const q = query.trim();
  if (q.length < 2) return [];
  const { data } = await supabase
    .from("artists")
    .select("artist_id, artist_name")
    .ilike("artist_name", `%${escapeLike(q)}%`)
    .order("artist_name")
    .limit(8);
  return data ?? [];
}

/** Follow an artist by name, creating the artist if it doesn't exist yet (manual entry needs no external API). */
export async function followArtist(rawName: string): Promise<ActionResult> {
  const v = validateArtistName(rawName);
  if (!v.ok) return { error: v.error };
  const { supabase, user } = await requireUser();

  const find = () => supabase.from("artists").select("artist_id").ilike("artist_name", escapeLike(v.name)).maybeSingle();
  let { data: artist } = await find();
  if (!artist) {
    const ins = await supabase.from("artists").insert({ artist_name: v.name }).select("artist_id").single();
    if (ins.error?.code === "23505") artist = (await find()).data; // created concurrently
    else if (ins.error) return { error: "Couldn't add that artist. Try again." };
    else artist = ins.data;
  }
  if (!artist) return { error: "Couldn't add that artist. Try again." };

  const { error } = await supabase.from("user_artists").insert({ user_id: user.id, artist_id: artist.artist_id });
  if (error && error.code !== "23505") return { error: "Couldn't follow that artist. Try again." };
  revalidatePath("/", "layout");
  return {};
}

export async function unfollowArtist(artistId: string): Promise<ActionResult> {
  const { supabase, user } = await requireUser();
  const { error } = await supabase.from("user_artists").delete().eq("user_id", user.id).eq("artist_id", artistId);
  if (error) return { error: "Couldn't unfollow. Try again." };
  revalidatePath("/", "layout");
  return {};
}

/** Follow an existing artist by id (used by the A-Z browser; avoids matching on names with symbols like P!nk or KR$NA). */
export async function followArtistById(artistId: string): Promise<ActionResult> {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(artistId)) return { error: "Unknown artist." };
  const { supabase, user } = await requireUser();
  const { error } = await supabase.from("user_artists").insert({ user_id: user.id, artist_id: artistId });
  if (error && error.code !== "23505") return { error: "Couldn't follow that artist. Try again." };
  revalidatePath("/", "layout");
  return {};
}


const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export type SaveResult = { error?: string; added?: number; removed?: number };

/** Save a staged selection in one go: follow existing artists (ids), follow typed names (created if new), unfollow ids. */
export async function saveArtistChanges(input: { addIds: string[]; addNames: string[]; removeIds: string[] }): Promise<SaveResult> {
  const addIds = [...new Set(input.addIds ?? [])];
  const removeIds = [...new Set(input.removeIds ?? [])];
  const names = [...new Map((input.addNames ?? []).map((n) => [n.replace(/\s+/g, " ").trim().toLowerCase(), n]) ).values()];
  if (addIds.length + names.length + removeIds.length > 300) return { error: "Too many changes at once." };
  if ([...addIds, ...removeIds].some((id) => !UUID.test(id))) return { error: "Unknown artist." };
  const validated = names.map(validateArtistName);
  const bad = validated.find((v) => !v.ok);
  if (bad && !bad.ok) return { error: bad.error };

  const { supabase, user } = await requireUser();
  const ids = new Set(addIds);
  for (const v of validated) {
    if (!v.ok) continue;
    const find = () => supabase.from("artists").select("artist_id").ilike("artist_name", escapeLike(v.name)).maybeSingle();
    let { data: artist } = await find();
    if (!artist) {
      const ins = await supabase.from("artists").insert({ artist_name: v.name }).select("artist_id").single();
      if (ins.error?.code === "23505") artist = (await find()).data;
      else if (ins.error) return { error: `Couldn't add ${v.name}. Nothing was saved for it.` };
      else artist = ins.data;
    }
    if (artist) ids.add(artist.artist_id);
  }
  if (ids.size) {
    const { error } = await supabase.from("user_artists")
      .upsert([...ids].map((artist_id) => ({ user_id: user.id, artist_id })), { onConflict: "user_id,artist_id", ignoreDuplicates: true });
    if (error) return { error: "Couldn't save your artists. Try again." };
  }
  if (removeIds.length) {
    const { error } = await supabase.from("user_artists").delete().eq("user_id", user.id).in("artist_id", removeIds);
    if (error) return { error: "Couldn't remove some artists. Try again." };
  }
  revalidatePath("/", "layout");
  return { added: ids.size, removed: removeIds.length };
}

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

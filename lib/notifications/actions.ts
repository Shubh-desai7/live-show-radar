"use server";

import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth/session";
import { createAdminClient } from "@/lib/supabase/admin";
import { generateToken, hashToken, TOKEN_TTL_MS } from "./link-token";

export type LinkResult = { url?: string; error?: string };

/** Create a single-use, 15-minute link token and return the t.me deep link. Previous unused tokens are revoked. */
export async function createTelegramLink(): Promise<LinkResult> {
  const username = process.env.TELEGRAM_BOT_USERNAME?.replace(/^@/, "");
  if (!username) return { error: "Telegram isn't set up on this server yet." };
  const { user } = await requireUser();
  const db = createAdminClient();
  await db.from("telegram_link_tokens").delete().eq("user_id", user.id).is("used_at", null);
  const token = generateToken();
  const { error } = await db.from("telegram_link_tokens").insert({
    token_hash: hashToken(token),
    user_id: user.id,
    expires_at: new Date(Date.now() + TOKEN_TTL_MS).toISOString(),
  });
  if (error) return { error: "Couldn't create a link. Try again." };
  return { url: `https://t.me/${username}?start=${token}` };
}

export async function disconnectTelegram(): Promise<{ error?: string }> {
  const { user } = await requireUser();
  // Users can't write telegram_chat_id themselves (column privilege), so this runs as the service role for this user only.
  const { error } = await createAdminClient().from("profiles").update({ telegram_chat_id: null }).eq("user_id", user.id);
  if (error) return { error: "Couldn't disconnect. Try again." };
  revalidatePath("/", "layout");
  return {};
}

export async function refreshTelegramStatus(): Promise<void> {
  await requireUser();
  revalidatePath("/", "layout");
}

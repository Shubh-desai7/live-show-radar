import "server-only";
import { createAdminClient } from "@/lib/supabase/admin";
import { sendTelegramMessage } from "./telegram-api";
import type { WebhookDeps } from "./webhook";

/** Real implementation of the webhook's dependencies (service role: bypasses RLS, server-only). */
export function realDeps(): WebhookDeps {
  const db = createAdminClient();
  return {
    async consumeToken(hash, now) {
      // One atomic UPDATE: only an unused, unexpired token matches, so a token can be consumed exactly once.
      const { data } = await db
        .from("telegram_link_tokens")
        .update({ used_at: now.toISOString() })
        .eq("token_hash", hash)
        .is("used_at", null)
        .gt("expires_at", now.toISOString())
        .select("user_id")
        .maybeSingle();
      return data ? { userId: data.user_id as string } : null;
    },
    async linkChat(userId, chatId) {
      // A chat belongs to one account: detach it from any other profile first (unique constraint).
      await db.from("profiles").update({ telegram_chat_id: null }).eq("telegram_chat_id", chatId);
      const { error } = await db.from("profiles").update({ telegram_chat_id: chatId }).eq("user_id", userId);
      if (error) throw new Error("linkChat failed");
    },
    async unlinkChat(chatId) {
      const { data } = await db.from("profiles").update({ telegram_chat_id: null }).eq("telegram_chat_id", chatId).select("user_id");
      return (data?.length ?? 0) > 0;
    },
    send: async (chatId, text) => { await sendTelegramMessage(chatId, text); },
  };
}

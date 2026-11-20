import { secretMatches } from "@/lib/notifications/link-token";
import { realDeps } from "@/lib/notifications/telegram-deps";
import { handleUpdate } from "@/lib/notifications/webhook";

/** Telegram -> us. Authenticated by the secret token we registered with setWebhook. */
export async function POST(request: Request) {
  if (!secretMatches(request.headers.get("x-telegram-bot-api-secret-token"), process.env.TELEGRAM_WEBHOOK_SECRET)) {
    return new Response("unauthorized", { status: 401 });
  }
  let update: unknown;
  try {
    update = await request.json();
  } catch {
    return new Response("bad request", { status: 400 });
  }
  try {
    await handleUpdate(update, realDeps(), new Date());
  } catch (e) {
    // Always answer 200 so Telegram doesn't retry-storm; the message never contains tokens or user content.
    console.error("telegram webhook error:", e instanceof Error ? e.message : "unknown");
  }
  return new Response("ok");
}

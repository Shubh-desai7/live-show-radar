import "server-only";

/** Send a plain-text message. Never throws and never logs the bot token. Used only for webhook replies;
 *  alert delivery is done by the Python worker. */
export async function sendTelegramMessage(chatId: number, text: string): Promise<boolean> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) {
    console.warn("TELEGRAM_BOT_TOKEN not set: reply skipped");
    return false;
  }
  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text, disable_web_page_preview: true }),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) console.warn("Telegram sendMessage failed with HTTP", res.status);
    return res.ok;
  } catch {
    console.warn("Telegram sendMessage network error");
    return false;
  }
}

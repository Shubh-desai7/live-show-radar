// Register / inspect / remove the Telegram webhook. Usage:
//   node --env-file=.env.local scripts/telegram-webhook.mjs set https://your-app.vercel.app
//   node --env-file=.env.local scripts/telegram-webhook.mjs info
//   node --env-file=.env.local scripts/telegram-webhook.mjs delete
// The bot token is read from the environment and never printed.
const [cmd, base] = process.argv.slice(2);
const token = process.env.TELEGRAM_BOT_TOKEN;
const secret = process.env.TELEGRAM_WEBHOOK_SECRET;
if (!token) { console.error("TELEGRAM_BOT_TOKEN is not set"); process.exit(1); }

const call = async (method, body) => {
  const res = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}),
  });
  const json = await res.json();
  return json;
};

if (cmd === "set") {
  if (!base?.startsWith("https://")) { console.error("Give the public https:// base URL of the deployed app"); process.exit(1); }
  if (!secret) { console.error("TELEGRAM_WEBHOOK_SECRET is not set"); process.exit(1); }
  const r = await call("setWebhook", { url: `${base.replace(/\/$/, "")}/api/telegram/webhook`, secret_token: secret, allowed_updates: ["message"], drop_pending_updates: true });
  console.log(r.ok ? "Webhook set." : "Failed: " + r.description);
} else if (cmd === "info") {
  const r = await call("getWebhookInfo");
  const { url, pending_update_count, last_error_message } = r.result ?? {};
  console.log(JSON.stringify({ url, pending_update_count, last_error_message }, null, 2));
} else if (cmd === "delete") {
  console.log((await call("deleteWebhook")).ok ? "Webhook removed." : "Failed.");
} else {
  console.error("Usage: set <https-base-url> | info | delete"); process.exit(1);
}

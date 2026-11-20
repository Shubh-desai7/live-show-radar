import { hashToken, isPlausibleToken, parseStart } from "./link-token";

/** Everything the webhook needs from the outside world, injected so the logic is unit-testable. */
export type WebhookDeps = {
  /** Atomically consume an unused, unexpired token hash. Returns the user it belongs to, or null. */
  consumeToken(hash: string, now: Date): Promise<{ userId: string } | null>;
  linkChat(userId: string, chatId: number): Promise<void>;
  unlinkChat(chatId: number): Promise<boolean>;
  send(chatId: number, text: string): Promise<void>;
};

export const MESSAGES = {
  linked:
    "You're connected to Live Show Radar. I'll message you about announcements, presales and ticket sales for the artists and cities you follow. Delivery isn't instant. Send /stop any time to disconnect.",
  invalid: "That link is invalid, already used or has expired. Open Live Show Radar → Settings and press “Connect Telegram” to get a new one.",
  privateOnly: "Please link your account in a private chat with me, not in a group.",
  stopped: "Disconnected. You won't get alerts here any more. You can reconnect from Settings.",
  notLinked: "This chat isn't connected to an account.",
  help: "To connect, open Live Show Radar → Settings → “Connect Telegram”. Commands: /stop disconnects this chat.",
} as const;

type Update = { message?: { text?: string; chat?: { id?: number; type?: string } } };

export async function handleUpdate(raw: unknown, deps: WebhookDeps, now: Date): Promise<void> {
  const msg = (raw as Update | null)?.message;
  const chatId = msg?.chat?.id;
  if (typeof chatId !== "number") return;                 // not a message we handle
  const reply = (text: string) => deps.send(chatId, text);

  const text = msg?.text?.trim();
  const start = parseStart(text);

  if (start !== undefined) {
    if (msg?.chat?.type !== "private") return reply(MESSAGES.privateOnly);
    if (start === null || !isPlausibleToken(start)) return reply(start === null ? MESSAGES.help : MESSAGES.invalid);
    const owner = await deps.consumeToken(hashToken(start), now);
    if (!owner) return reply(MESSAGES.invalid);
    await deps.linkChat(owner.userId, chatId);
    return reply(MESSAGES.linked);
  }
  if (text && /^\/stop(?:@\w+)?$/.test(text)) {
    return reply((await deps.unlinkChat(chatId)) ? MESSAGES.stopped : MESSAGES.notLinked);
  }
  if (msg?.chat?.type === "private") return reply(MESSAGES.help);
}

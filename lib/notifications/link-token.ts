import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

export const TOKEN_TTL_MS = 15 * 60 * 1000;

/** 32 random bytes as base64url = 43 chars, within Telegram's 64-char /start parameter limit. */
export function generateToken(): string {
  return randomBytes(32).toString("base64url");
}

/** Only the hash is stored, so a database leak can't be replayed. */
export function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

export function isPlausibleToken(token: string): boolean {
  return /^[A-Za-z0-9_-]{43}$/.test(token);
}

/** "/start <token>" -> token; bare "/start" -> null; anything else -> undefined. Handles "/start@BotName". */
export function parseStart(text: string | undefined): string | null | undefined {
  if (!text) return undefined;
  const m = /^\/start(?:@\w+)?(?:\s+(\S+))?\s*$/.exec(text.trim());
  if (!m) return undefined;
  return m[1] ?? null;
}

/** Constant-time check of Telegram's X-Telegram-Bot-Api-Secret-Token header. Rejects when no secret is configured. */
export function secretMatches(header: string | null, expected: string | undefined): boolean {
  if (!expected || !header) return false;
  const a = createHash("sha256").update(header).digest();
  const b = createHash("sha256").update(expected).digest();
  return timingSafeEqual(a, b);
}

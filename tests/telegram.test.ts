import { describe, expect, it } from "vitest";
import { generateToken, hashToken, isPlausibleToken, parseStart, secretMatches } from "@/lib/notifications/link-token";
import { handleUpdate, MESSAGES, type WebhookDeps } from "@/lib/notifications/webhook";

describe("link tokens", () => {
  it("are 43-char url-safe, unique, and stored only as a hash", () => {
    const a = generateToken(), b = generateToken();
    expect(isPlausibleToken(a)).toBe(true);
    expect(a).not.toBe(b);
    expect(hashToken(a)).toMatch(/^[0-9a-f]{64}$/);
    expect(hashToken(a)).not.toContain(a);
  });
  it("rejects malformed tokens", () => {
    for (const t of ["", "short", "a".repeat(42), "a".repeat(44), "!".repeat(43)]) expect(isPlausibleToken(t)).toBe(false);
  });
});

describe("parseStart", () => {
  it("extracts the token, handles bare and addressed /start, ignores other text", () => {
    expect(parseStart("/start abc")).toBe("abc");
    expect(parseStart("/start@LiveBot abc")).toBe("abc");
    expect(parseStart("/start")).toBeNull();
    expect(parseStart("hello")).toBeUndefined();
    expect(parseStart(undefined)).toBeUndefined();
    expect(parseStart("/start a b")).toBeUndefined();
  });
});

describe("webhook secret", () => {
  it("matches only the exact secret and never when unconfigured", () => {
    expect(secretMatches("s3cret", "s3cret")).toBe(true);
    expect(secretMatches("s3cre", "s3cret")).toBe(false);
    expect(secretMatches(null, "s3cret")).toBe(false);
    expect(secretMatches("anything", undefined)).toBe(false);
    expect(secretMatches("", "")).toBe(false);
  });
});

function fakeDeps(validHash?: string) {
  const sent: string[] = [], linked: [string, number][] = [], used = new Set<string>();
  const deps: WebhookDeps = {
    async consumeToken(hash) {
      if (hash !== validHash || used.has(hash)) return null;
      used.add(hash);
      return { userId: "u1" };
    },
    async linkChat(u, c) { linked.push([u, c]); },
    async unlinkChat() { return true; },
    async send(_c, t) { sent.push(t); },
  };
  return { deps, sent, linked };
}
const upd = (text: string, type = "private") => ({ message: { text, chat: { id: 42, type } } });
const now = new Date();

describe("handleUpdate", () => {
  it("links the chat with a valid token, and the token works exactly once", async () => {
    const token = generateToken();
    const f = fakeDeps(hashToken(token));
    await handleUpdate(upd("/start " + token), f.deps, now);
    expect(f.linked).toEqual([["u1", 42]]);
    expect(f.sent).toEqual([MESSAGES.linked]);
    await handleUpdate(upd("/start " + token), f.deps, now);
    expect(f.linked).toHaveLength(1);
    expect(f.sent[1]).toBe(MESSAGES.invalid);
  });
  it("never links on a wrong or malformed token", async () => {
    const f = fakeDeps(hashToken(generateToken()));
    await handleUpdate(upd("/start " + generateToken()), f.deps, now);
    await handleUpdate(upd("/start nope"), f.deps, now);
    expect(f.linked).toEqual([]);
    expect(f.sent).toEqual([MESSAGES.invalid, MESSAGES.invalid]);
  });
  it("refuses to link in group chats", async () => {
    const token = generateToken();
    const f = fakeDeps(hashToken(token));
    await handleUpdate(upd("/start " + token, "group"), f.deps, now);
    expect(f.linked).toEqual([]);
    expect(f.sent).toEqual([MESSAGES.privateOnly]);
  });
  it("answers bare /start with help, handles /stop, and ignores junk", async () => {
    const f = fakeDeps();
    await handleUpdate(upd("/start"), f.deps, now);
    await handleUpdate(upd("/stop"), f.deps, now);
    await handleUpdate(upd("hi there"), f.deps, now);
    expect(f.sent).toEqual([MESSAGES.help, MESSAGES.stopped, MESSAGES.help]);
    for (const junk of [null, {}, { message: {} }, { message: { chat: { id: "x" } } }, "str"]) await handleUpdate(junk, f.deps, now);
    expect(f.sent).toHaveLength(3);
  });
});

import { describe, expect, it } from "vitest";
import { escapeLike, isOnboarded, normalizeArtistName, validateArtistName } from "@/lib/artists/validate";
import { isKnownCity } from "@/lib/cities";

describe("artist validation", () => {
  it("collapses whitespace", () => expect(normalizeArtistName("  Prateek   Kuhad ")).toBe("Prateek Kuhad"));
  it("rejects empty and over-long names", () => {
    expect(validateArtistName("   ").ok).toBe(false);
    expect(validateArtistName("x".repeat(121)).ok).toBe(false);
    expect(validateArtistName(" Nucleya ")).toEqual({ ok: true, name: "Nucleya" });
  });
  it("escapes ILIKE wildcards", () => expect(escapeLike("100%_a\\")).toBe("100\\%\\_a\\\\"));
});

describe("onboarding", () => {
  it("needs at least one artist and one city", () => {
    expect(isOnboarded(0, 1)).toBe(false);
    expect(isOnboarded(1, 0)).toBe(false);
    expect(isOnboarded(2, 1)).toBe(false);
    expect(isOnboarded(3, 0)).toBe(false);
    expect(isOnboarded(3, 1)).toBe(true);
  });
  it("knows Bengaluru", () => expect(isKnownCity("Bengaluru")).toBe(true));
});

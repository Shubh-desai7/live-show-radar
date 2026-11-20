import { describe, expect, it } from "vitest";
import { isOfficiallyConfirmed, isUserVisible } from "@/lib/events/status";

describe("verification states", () => {
  it("never shows rumoured events to users", () => {
    expect(isUserVisible("rumoured")).toBe(false);
    expect(isUserVisible("unconfirmed")).toBe(true);
    expect(isUserVisible("confirmed")).toBe(true);
  });
  it("only confirmed counts as officially confirmed", () => {
    expect(isOfficiallyConfirmed("confirmed")).toBe(true);
    expect(isOfficiallyConfirmed("unconfirmed")).toBe(false);
    expect(isOfficiallyConfirmed("rumoured")).toBe(false);
  });
});

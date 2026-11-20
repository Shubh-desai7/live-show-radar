import { describe, expect, it } from "vitest";
import {
  cityMatches, formatEventDate, formatMoment, isNewlyAnnounced, isUpcoming, nextDeadline, timeUntil, upcomingDeadlines, type TicketInfo,
} from "@/lib/events/dashboard";

const now = new Date("2026-12-01T10:00:00Z");
const t = (o: Partial<TicketInfo>): TicketInfo => ({
  presale_registration_deadline: null, presale_opening: null, general_sale_opening: null,
  early_bird_status: "unknown", booking_url: null, timing_reliable: true, ...o,
});

describe("deadlines", () => {
  it("returns only future moments, soonest first", () => {
    const d = upcomingDeadlines(t({
      presale_registration_deadline: "2026-11-30T10:00:00Z", // past
      presale_opening: "2026-12-05T10:00:00Z",
      general_sale_opening: "2026-12-03T10:00:00Z",
    }), now);
    expect(d.map((x) => x.kind)).toEqual(["general_sale", "presale_opening"]);
  });
  it("handles no tickets", () => {
    expect(nextDeadline(null, now)).toBeNull();
    expect(nextDeadline(t({}), now)).toBeNull();
  });
  it("describes time remaining", () => {
    expect(timeUntil(new Date("2026-12-01T12:00:00Z"), now)).toBe("in 2h");
    expect(timeUntil(new Date("2026-12-01T10:20:00Z"), now)).toBe("in 20 min");
    expect(timeUntil(new Date("2026-12-04T10:00:00Z"), now)).toBe("in 3 days");
  });
});

describe("events", () => {
  it("flags announcements from the last 7 days as new", () => {
    expect(isNewlyAnnounced("2026-11-28T00:00:00Z", now)).toBe(true);
    expect(isNewlyAnnounced("2026-11-20T00:00:00Z", now)).toBe(false);
  });
  it("matches cities case-insensitively and never matches unknown city", () => {
    expect(cityMatches("bengaluru", ["Bengaluru"])).toBe(true);
    expect(cityMatches(null, ["Bengaluru"])).toBe(false);
    expect(cityMatches("Pune", ["Bengaluru"])).toBe(false);
  });
  it("treats unknown or today/future dates as upcoming", () => {
    expect(isUpcoming(null, now)).toBe(true);
    expect(isUpcoming("2026-12-01", now)).toBe(true);
    expect(isUpcoming("2026-11-30", now)).toBe(false);
  });
  it("formats calendar dates without timezone drift", () => {
    expect(formatEventDate("2026-12-25")).toContain("25");
    expect(formatEventDate(null)).toBe("Date to be announced");
  });
});

describe("ticket moment display", () => {
  const iso = "2026-12-07T18:30:00Z"; // = 8 Dec 2026 00:00 IST (a stored date-only moment)
  it("shows only the IST calendar date when timing is unverified, whatever the user's timezone", () => {
    expect(formatMoment(iso, "America/New_York", false)).toBe("8 Dec 2026 (time not confirmed)");
  });
  it("shows the full local time when timing is verified", () => {
    expect(formatMoment("2026-12-08T12:30:00Z", "Asia/Kolkata", true)).toMatch(/8 Dec 2026/);
    expect(formatMoment("2026-12-08T12:30:00Z", "Asia/Kolkata", true)).toMatch(/6:00/);
  });
});

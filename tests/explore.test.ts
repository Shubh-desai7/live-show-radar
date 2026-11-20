import { describe, expect, it } from "vitest";
import { cityCounts, filterShows, groupByDate, type Show } from "@/lib/events/explore";

const S = (o: Partial<Show> & { id: string }): Show => ({ artist: "A", name: null, city: "Mumbai", venue: null, date: "2026-12-01", confidence: "confirmed", status: "scheduled", link: null, sourceType: null, ...o });
const shows = [
  S({ id: "1", artist: "Nucleya", city: "Bengaluru", date: "2026-12-05", venue: "Prism" }),
  S({ id: "2", artist: "Sunburn Festival", city: "Mumbai", date: "2026-12-18", confidence: "unconfirmed" }),
  S({ id: "3", artist: "Hornbill Music Festival", city: "Kisama", date: "2026-12-01" }),
  S({ id: "4", artist: "Tiësto", city: "Goa", date: null }),
];
const none = { city: null, query: "", officialOnly: false, withinDays: null };

describe("all-shows filters", () => {
  it("filters by city, official-only and search (accent-insensitive, matches venue)", () => {
    expect(filterShows(shows, { ...none, city: "Kisama" }, "2026-11-20").map((s) => s.id)).toEqual(["3"]);
    expect(filterShows(shows, { ...none, officialOnly: true }, "2026-11-20").map((s) => s.id)).toEqual(["1", "3", "4"]);
    expect(filterShows(shows, { ...none, query: "tiesto" }, "2026-11-20").map((s) => s.id)).toEqual(["4"]);
    expect(filterShows(shows, { ...none, query: "prism" }, "2026-11-20").map((s) => s.id)).toEqual(["1"]);
  });
  it("'within N days' keeps only dated shows inside the window", () => {
    expect(filterShows(shows, { ...none, withinDays: 20 }, "2026-11-20").map((s) => s.id)).toEqual(["1", "3"]);
  });
  it("counts shows per city, most first, and groups by date with undated last", () => {
    expect(cityCounts(shows)[0]).toEqual({ city: "Bengaluru", count: 1 });
    expect(cityCounts([...shows, S({ id: "5", city: "Mumbai" })])[0]).toEqual({ city: "Mumbai", count: 2 });
    expect(groupByDate(shows).map((g) => g.date)).toEqual(["2026-12-01", "2026-12-05", "2026-12-18", null]);
  });
});

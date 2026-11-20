import { describe, expect, it } from "vitest";
import { filterArtists, groupByLetter, letterCounts, letterOf, matchesQuery, type BrowseArtist } from "@/lib/artists/browse";

const A = (artist_name: string, region: BrowseArtist["region"] = "world"): BrowseArtist => ({ artist_id: artist_name, artist_name, region });
const data = [A("Arijit Singh", "india"), A("A. R. Rahman", "india"), A("Åsa"), A("2Cellos"), A("Tiësto"), A("The Weeknd"), A("KR$NA", "india"), A("P!nk")];

describe("A-Z browsing", () => {
  it("buckets by first letter, ignoring accents; digits and symbols go to #", () => {
    expect(letterOf("Arijit Singh")).toBe("A");
    expect(letterOf("Åsa")).toBe("A");
    expect(letterOf("Tiësto")).toBe("T");
    expect(letterOf("2Cellos")).toBe("#");
    expect(letterOf("  p!nk")).toBe("P");
    expect(letterOf("")).toBe("#");
  });
  it("does not drop 'The': it is part of the name", () => expect(letterOf("The Weeknd")).toBe("T"));
  it("searches ignoring case and accents", () => {
    expect(matchesQuery("Tiësto", "tiesto")).toBe(true);
    expect(matchesQuery("Arijit Singh", "RIJIT")).toBe(true);
    expect(matchesQuery("Arijit Singh", "zzz")).toBe(false);
    expect(matchesQuery("Anything", "")).toBe(true);
  });
  it("combines region, letter and query filters", () => {
    expect(filterArtists(data, { region: "india", letter: null, query: "" }).map((a) => a.artist_name)).toEqual(["Arijit Singh", "A. R. Rahman", "KR$NA"]);
    expect(filterArtists(data, { region: "all", letter: "A", query: "" })).toHaveLength(3);
    expect(filterArtists(data, { region: "india", letter: "A", query: "arijit" })).toHaveLength(1);
  });
  it("groups in alphabetical order with # last, and counts per letter", () => {
    const groups = groupByLetter(data);
    expect(groups.map((g) => g.letter)).toEqual(["A", "K", "P", "T", "#"]);
    expect(groups[0].artists.map((a) => a.artist_name)).toEqual(["A. R. Rahman", "Arijit Singh", "Åsa"]);
    expect(letterCounts(data)).toMatchObject({ A: 3, T: 2, "#": 1 });
  });
});

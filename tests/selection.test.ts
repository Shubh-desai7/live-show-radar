import { describe, expect, it } from "vitest";
import { dedupeNames, diffSets } from "@/lib/artists/selection";

describe("staged selection", () => {
  it("computes additions and removals against the saved set", () => {
    const d = diffSets(new Set(["a", "b", "c"]), new Set(["b", "c", "d", "e"]));
    expect(d.add.sort()).toEqual(["d", "e"]);
    expect(d.remove).toEqual(["a"]);
  });
  it("reports no change when selection equals saved", () => {
    expect(diffSets(new Set(["a"]), new Set(["a"]))).toEqual({ add: [], remove: [] });
    expect(diffSets(new Set<string>(), new Set<string>())).toEqual({ add: [], remove: [] });
  });
  it("dedupes typed names ignoring case and spacing", () => {
    expect(dedupeNames(["  Nucleya", "nucleya ", "Prateek   Kuhad", "", "  "])).toEqual(["Nucleya", "Prateek Kuhad"]);
  });
});

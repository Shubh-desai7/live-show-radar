import { describe, expect, it } from "vitest";
import { coverageFor } from "@/lib/artists/coverage";

const a = (site_status?: string) => ({ official_website: null, metadata: site_status ? { site_status } : null });

describe("coverage status", () => {
  it("is good as soon as at least one page is being checked", () => {
    expect(coverageFor({ official_website: "https://x.example/", metadata: { site_status: "ok" } }, 2).tone).toBe("good");
    expect(coverageFor(a("none"), 1).tone).toBe("good");
  });
  it("explains each way a site can fail", () => {
    expect(coverageFor(a("none"), 0).label).toMatch(/No official site/);
    expect(coverageFor(a("blocked"), 0).label).toMatch(/blocks automated/);
    expect(coverageFor(a("unverified"), 0).tone).toBe("warn");
    expect(coverageFor(a("ambiguous"), 0).tone).toBe("warn");
    expect(coverageFor(a("error"), 0).label).toMatch(/retry/);
  });
  it("says not checked yet when nothing is known", () => {
    expect(coverageFor(a(), 0).label).toBe("Not checked yet");
    expect(coverageFor({ official_website: null, metadata: { site_status: 5 } }, 0).tone).toBe("idle");
  });
});

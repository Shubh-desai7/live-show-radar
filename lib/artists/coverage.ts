/** Plain-language status of how (and whether) we can watch an artist. Derived from what the worker stored. */
export type CoverageInput = { official_website: string | null; metadata: Record<string, unknown> | null };

export type Coverage = { label: string; detail: string; tone: "good" | "warn" | "bad" | "idle" };

export function coverageFor(a: CoverageInput, sourceCount: number): Coverage {
  const status = typeof a.metadata?.site_status === "string" ? a.metadata.site_status : null;
  if (sourceCount > 0) {
    return { label: "Official page checked", tone: "good",
      detail: "We re-read their official page every ~30 minutes. If it loads its tour list with a widget (Bandsintown, Songkick, Seated...) we can't see those shows." };
  }
  switch (status) {
    case "none": return { label: "No official site on record", tone: "bad", detail: "We couldn't find an official website for them, so we can only catch them on promoter pages." };
    case "blocked": return { label: "Their site blocks automated reading", tone: "bad", detail: "We respect that. We can only catch them on promoter pages." };
    case "unverified":
    case "ambiguous": return { label: "Couldn't verify their official site", tone: "warn", detail: "A site was suggested but we couldn't confirm it is really theirs, so we don't use it." };
    case "error": return { label: "Site check failed, will retry", tone: "warn", detail: "We'll try again automatically." };
    default: return { label: "Not checked yet", tone: "idle", detail: "Their site is looked up in the next few runs (about 30 minutes each)." };
  }
}

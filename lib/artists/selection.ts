/** Staged-selection helpers: the UI edits locally and only a Save writes to the database. */
export function diffSets<T>(saved: ReadonlySet<T>, selected: ReadonlySet<T>): { add: T[]; remove: T[] } {
  return {
    add: [...selected].filter((x) => !saved.has(x)),
    remove: [...saved].filter((x) => !selected.has(x)),
  };
}

/** Unique, trimmed names (case-insensitive), preserving first spelling. */
export function dedupeNames(names: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of names) {
    const n = raw.replace(/\s+/g, " ").trim();
    if (n && !seen.has(n.toLowerCase())) { seen.add(n.toLowerCase()); out.push(n); }
  }
  return out;
}

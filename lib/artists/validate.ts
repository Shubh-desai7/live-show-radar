export function normalizeArtistName(raw: string): string {
  return raw.replace(/\s+/g, " ").trim();
}

export function validateArtistName(raw: string): { ok: true; name: string } | { ok: false; error: string } {
  const name = normalizeArtistName(raw);
  if (!name) return { ok: false, error: "Enter an artist name." };
  if (name.length > 120) return { ok: false, error: "Artist name is too long (max 120 characters)." };
  return { ok: true, name };
}

/** Escape LIKE/ILIKE wildcards so user input is matched literally. */
export function escapeLike(q: string): string {
  return q.replace(/[\\%_]/g, (c) => "\\" + c);
}

/** A user is onboarded once they follow at least one artist and track at least one city. */
export function isOnboarded(artistCount: number, cityCount: number): boolean {
  return artistCount > 0 && cityCount > 0;
}

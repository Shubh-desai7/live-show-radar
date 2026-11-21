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

/** Minimum artists to follow before the radar opens (enough for the recommendations and alerts to be useful). */
export const MIN_ARTISTS = 3;

/** A user is onboarded once they follow at least MIN_ARTISTS artists and track at least one city. */
export function isOnboarded(artistCount: number, cityCount: number): boolean {
  return artistCount >= MIN_ARTISTS && cityCount > 0;
}

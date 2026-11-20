/** Verification states. See CLAUDE.md "Verification states". */
export type Confidence = "confirmed" | "unconfirmed" | "rumoured";

/** Rumoured events are internal only and must never be shown as events. */
export function isUserVisible(confidence: Confidence): boolean {
  return confidence !== "rumoured";
}

/** Only confirmed events may be presented as officially confirmed or trigger normal event alerts. */
export function isOfficiallyConfirmed(confidence: Confidence): boolean {
  return confidence === "confirmed";
}

export const confidenceLabel: Record<Exclude<Confidence, "rumoured">, string> = {
  confirmed: "Confirmed",
  unconfirmed: "Unconfirmed",
};

/** Narrow to a state that may be rendered; rumoured has no visible form. */
export function toVisible(c: Confidence): Exclude<Confidence, "rumoured"> | null {
  return c === "rumoured" ? null : c;
}

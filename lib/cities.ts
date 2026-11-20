/** Selectable Indian cities. Bengaluru is the launch city and is listed first. */
export const INDIAN_CITIES = [
  "Bengaluru", "Mumbai", "Delhi NCR", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad",
  "Goa", "Jaipur", "Chandigarh", "Kochi", "Lucknow", "Indore", "Guwahati", "Shillong",
] as const;

export function isKnownCity(city: string): boolean {
  return (INDIAN_CITIES as readonly string[]).includes(city);
}

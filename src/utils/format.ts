/** Converts a string to Title Case: first letter of each word capitalized. */
export function toTitleCase(s: string | null | undefined): string {
  if (!s) return "";
  return s.toLowerCase().replace(/(?:^|[\s])[\S]/g, c => c.toUpperCase());
}

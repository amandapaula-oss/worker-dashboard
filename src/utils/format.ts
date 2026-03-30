const MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];

/** Formats a "YYYY-MM" period string to "Mmm/YY" (e.g. "2025-10" → "Out/25"). */
export function periodoLabel(p: string): string {
  const [y, m] = p.split("-");
  return `${MESES[parseInt(m, 10) - 1] ?? m}/${y.slice(2)}`;
}

/** Converts a string to Title Case: first letter of each word capitalized.
 *  Short all-caps tokens (2–4 chars, e.g. "BMG", "S.A.", "CBMM") are kept as-is. */
export function toTitleCase(s: string | null | undefined): string {
  if (!s) return "";
  return s.split(/(\s+)/).map(part => {
    if (/^\s+$/.test(part)) return part;
    // Preserve short all-caps abbreviations/acronyms (BMG, S.A., CBMM, LTD…)
    if (part.length >= 2 && part.length <= 4 && part === part.toUpperCase() && /[A-Z]/.test(part)) return part;
    return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
  }).join("");
}

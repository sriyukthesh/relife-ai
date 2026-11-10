/** Pure formatting helpers shared by all grids (no AG Grid or React imports; easy to unit test). */

export const CONDITIONS = ["unverified", "tested_ok", "suspect_damaged"] as const;
export type Condition = (typeof CONDITIONS)[number];

export const CONDITION_LABEL: Record<Condition, string> = {
  unverified: "Not tested",
  tested_ok: "Tested by you",
  suspect_damaged: "Suspect / damaged",
};

export const conditionLabel = (c: unknown): string =>
  CONDITION_LABEL[c as Condition] ?? String(c ?? "");

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 });
/** Prices are stored in minor units (paise). */
export const moneyFromCents = (cents: unknown): string => {
  const n = Number(cents);
  return Number.isFinite(n) ? inr.format(n / 100) : "";
};

export const titleCase = (s: unknown): string =>
  String(s ?? "").replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());

/** {resistance_ohm: 220, color: "red"} -> "resistance ohm: 220 · color: red" */
export function specsText(specs: unknown): string {
  if (!specs || typeof specs !== "object") return "";
  const entries = Object.entries(specs as Record<string, unknown>);
  return entries.length ? entries.map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ") : "no details";
}

export const percent = (v: unknown): string => {
  const n = Number(v);
  return v == null || !Number.isFinite(n) ? "" : `${Math.round(n * 100)}%`;
};

export const shortDate = (iso: unknown): string => {
  const d = new Date(String(iso ?? ""));
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
};

/** Why a part is not used in recommendations (empty string = it is used). */
export function unusableReason(row: { usable: boolean; condition: string; missing_specs: string[] }): string {
  if (row.condition === "suspect_damaged") return "Suspect: excluded from builds";
  if (row.missing_specs.length > 0) return `Missing: ${row.missing_specs.join(", ")}`;
  return row.usable ? "" : "Excluded";
}

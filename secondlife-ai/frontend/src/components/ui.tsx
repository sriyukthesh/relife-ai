import type { ReactNode } from "react";
import { ApiError } from "../api";
import type { Condition } from "../types";

export const money = (cents: number) => `₹${(cents / 100).toFixed(2)}`;

export function errText(e: unknown): string {
  if (e instanceof ApiError) {
    const d = e.detail as { message?: string; missing_parts?: { label: string; quantity: number }[] } | string;
    if (typeof d === "object" && d?.missing_parts) {
      return `${d.message} Missing: ${d.missing_parts.map((m) => `${m.quantity} x ${m.label}`).join(", ")}`;
    }
    return e.message;
  }
  return e instanceof Error ? e.message : "Something went wrong";
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return <div role="alert" className="mb-3 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">{message}</div>;
}

export function Notice({ children }: { children: ReactNode }) {
  return <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">{children}</div>;
}

const COND: Record<Condition, { label: string; cls: string }> = {
  unverified: { label: "Not tested", cls: "bg-amber-100 text-amber-800" },
  tested_ok: { label: "Tested by you", cls: "bg-emerald-100 text-emerald-800" },
  suspect_damaged: { label: "Suspect / damaged", cls: "bg-red-100 text-red-800" },
};
export function ConditionBadge({ condition }: { condition: string }) {
  const c = COND[condition as Condition] ?? { label: condition, cls: "bg-stone-100 text-stone-700" };
  return <span className={`badge ${c.cls}`}>{c.label}</span>;
}
export const conditionLabel = (c: Condition) => COND[c].label;

export function specLine(specs: Record<string, string | number>): string {
  const e = Object.entries(specs);
  return e.length ? e.map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ") : "no details";
}

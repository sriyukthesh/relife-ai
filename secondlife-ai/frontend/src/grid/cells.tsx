import type { CustomCellRendererProps } from "ag-grid-react";
import { CONDITION_LABEL, type Condition } from "./format";

const BADGE: Record<Condition, string> = {
  unverified: "bg-amber-100 text-amber-800",
  tested_ok: "bg-emerald-100 text-emerald-800",
  suspect_damaged: "bg-red-100 text-red-800",
};

/** Colour-coded condition pill. */
export function ConditionCell(p: CustomCellRendererProps) {
  const c = p.value as Condition;
  const cls = BADGE[c] ?? "bg-stone-100 text-stone-700";
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{CONDITION_LABEL[c] ?? String(p.value ?? "")}</span>;
}

/** "Used in builds" status: green tick or the reason a part is excluded. */
export function UsableCell(p: CustomCellRendererProps) {
  const reason = String(p.value ?? "");
  return reason
    ? <span className="text-xs text-red-700">{reason}</span>
    : <span className="text-xs text-emerald-700">✓ Used in builds</span>;
}

export interface ActionContext<T> {
  onAction?: (row: T) => void;
  actionLabel?: string;
}

/** A button that calls context.onAction(row). Disabled for your own listings. */
export function ActionCell(p: CustomCellRendererProps) {
  const ctx = (p.context ?? {}) as ActionContext<unknown>;
  const mine = Boolean((p.data as { mine?: boolean } | undefined)?.mine);
  return (
    <button
      disabled={mine}
      onClick={() => p.data && ctx.onAction?.(p.data)}
      className="rounded-md bg-emerald-700 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-800 disabled:opacity-40"
    >
      {mine ? "Your listing" : ctx.actionLabel ?? "Add to cart"}
    </button>
  );
}

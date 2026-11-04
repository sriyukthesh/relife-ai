import { useState } from "react";
import type { Catalog, Condition, InventoryIn, Proposal, Specs } from "../types";
import { ConditionBadge, conditionLabel, errText, ErrorBanner } from "./ui";

export interface Draft extends Pick<Proposal, "category" | "label" | "quantity" | "specs"> {
  condition: Condition;
  confidence: number | null;
  evidence: string;
  uncertainties: string[];
  damage_flags: string[];
  needs_review: boolean;
  visible_markings: string;
}

export const blankDraft = (): Draft => ({
  category: "resistor", label: "", quantity: 1, specs: {}, condition: "unverified", confidence: null,
  evidence: "", uncertainties: [], damage_flags: [], needs_review: false, visible_markings: "",
});

export const draftFromProposal = (p: Proposal): Draft => ({
  category: p.category, label: p.label, quantity: p.quantity, specs: p.specs,
  condition: p.suggested_condition, confidence: p.ai_confidence, evidence: p.evidence,
  uncertainties: p.uncertainties, damage_flags: p.damage_flags, needs_review: p.needs_review,
  visible_markings: p.visible_markings,
});

interface Props {
  draft: Draft;
  catalog: Catalog;
  source: "scan" | "manual";
  index?: number;
  onConfirm: (item: InventoryIn) => Promise<void>;
  onSkip: () => void;
}

/** The human-confirmation step: nothing reaches inventory until the user presses Confirm. */
export default function ConfirmCard({ draft, catalog, source, index, onConfirm, onSkip }: Props) {
  const [category, setCategory] = useState(draft.category);
  const [label, setLabel] = useState(draft.label);
  const [quantity, setQuantity] = useState(draft.quantity);
  const [condition, setCondition] = useState<Condition>(draft.condition);
  const [vals, setVals] = useState<Record<string, string>>(
    Object.fromEntries(Object.entries(draft.specs).map(([k, v]) => [k, String(v)])),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const required = catalog.categories[category]?.required ?? [];
  const shown = Object.keys(catalog.spec_fields).filter((k) => required.includes(k) || vals[k]);
  const hidden = Object.keys(catalog.spec_fields).filter((k) => !shown.includes(k));

  const buildSpecs = (): Specs => {
    const out: Specs = {};
    for (const [k, raw] of Object.entries(vals)) {
      const v = String(raw).trim();
      if (!v) continue;
      const f = catalog.spec_fields[k];
      if (f?.type === "number") {
        const n = Number(v);
        if (Number.isFinite(n)) out[k] = n;
      } else out[k] = v;
    }
    return out;
  };

  const field = (k: string) => {
    const f = catalog.spec_fields[k];
    const isReq = required.includes(k);
    return (
      <label key={k} className="block text-sm">
        <span className="mb-1 block text-stone-600">
          {f.label}{f.unit ? ` (${f.unit})` : ""}{isReq && <span className="text-red-600"> *</span>}
        </span>
        {f.type === "choice" ? (
          <select className="input" value={vals[k] ?? ""} onChange={(e) => setVals({ ...vals, [k]: e.target.value })}>
            <option value="">unknown</option>
            {f.choices?.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        ) : (
          <input className="input" inputMode={f.type === "number" ? "decimal" : "text"} value={vals[k] ?? ""}
            onChange={(e) => setVals({ ...vals, [k]: e.target.value })} placeholder="unknown" />
        )}
      </label>
    );
  };

  const confirm = async () => {
    if (!label.trim()) { setError("Give the part a name."); return; }
    setBusy(true); setError(null);
    try {
      await onConfirm({
        category, label: label.trim(), specs: buildSpecs(), quantity, condition, source,
        ai_confidence: draft.confidence, ai_notes: draft.evidence || null, confirmed_by_user: true,
      });
    } catch (e) { setError(errText(e)); setBusy(false); }
  };

  return (
    <div className="card space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {index !== undefined && <span className="badge bg-stone-800 text-white">#{index + 1}</span>}
        {draft.confidence !== null && (
          <span className="badge bg-stone-100 text-stone-700">AI confidence {Math.round(draft.confidence * 100)}%</span>
        )}
        {draft.needs_review && <span className="badge bg-amber-100 text-amber-800">Please check carefully</span>}
        {draft.damage_flags.length > 0 && (
          <span className="badge bg-red-100 text-red-800">Possible damage: {draft.damage_flags.join(", ").replace(/_/g, " ")}</span>
        )}
      </div>

      {(draft.visible_markings || draft.evidence || draft.uncertainties.length > 0) && (
        <div className="rounded-lg bg-stone-50 p-2 text-xs text-stone-600">
          {draft.visible_markings && <p><b>Markings seen:</b> {draft.visible_markings}</p>}
          {draft.evidence && <p><b>AI reasoning:</b> {draft.evidence}</p>}
          {draft.uncertainties.length > 0 && <p><b>Not sure about:</b> {draft.uncertainties.join("; ")}</p>}
        </div>
      )}

      <ErrorBanner message={error} />
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block text-stone-600">Type</span>
          <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
            {Object.entries(catalog.categories).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-stone-600">Name</span>
          <input className="input" value={label} onChange={(e) => setLabel(e.target.value)} />
        </label>
        {shown.map(field)}
        <label className="block text-sm">
          <span className="mb-1 block text-stone-600">Quantity</span>
          <input className="input" type="number" min={1} value={quantity}
            onChange={(e) => setQuantity(Math.max(1, Number(e.target.value) || 1))} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-stone-600">Condition</span>
          <select className="input" value={condition} onChange={(e) => setCondition(e.target.value as Condition)}>
            {catalog.conditions.map((c) => <option key={c} value={c}>{conditionLabel(c)}</option>)}
          </select>
        </label>
      </div>
      <p className="text-xs text-stone-500">
        Choose “Tested by you” only if you checked this part with a meter or in a circuit. A photo cannot prove a part works.
        Current: <ConditionBadge condition={condition} />
      </p>
      {hidden.length > 0 && (
        <details className="text-sm"><summary className="cursor-pointer text-stone-600">More details</summary>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">{hidden.map(field)}</div>
        </details>
      )}
      <div className="flex gap-2">
        <button className="btn-primary" disabled={busy} onClick={confirm}>{busy ? "Saving…" : "Confirm & add to my parts"}</button>
        <button className="btn-ghost" disabled={busy} onClick={onSkip}>Skip</button>
      </div>
    </div>
  );
}

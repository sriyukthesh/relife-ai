import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { ConditionBadge, conditionLabel, errText, ErrorBanner, specLine } from "../components/ui";
import type { Catalog, Condition, InventoryItem } from "../types";

export default function Parts({ catalog, refreshKey }: { catalog: Catalog; refreshKey: number }) {
  const [items, setItems] = useState<InventoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setItems(await api.inventory()); setError(null); } catch (e) { setError(errText(e)); }
  }, []);
  useEffect(() => { load(); }, [load, refreshKey]);

  const run = async (fn: () => Promise<unknown>) => { try { await fn(); await load(); } catch (e) { setError(errText(e)); } };

  if (!items) return <><ErrorBanner message={error} /><p className="text-sm text-stone-500">Loading…</p></>;
  return (
    <div className="space-y-3">
      <ErrorBanner message={error} />
      {items.length === 0 && <p className="text-sm text-stone-600">No parts yet. Scan a photo or add one manually.</p>}
      {items.map((it) => (
        <div key={it.id} className="card flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <p className="font-medium">{it.label} <span className="text-stone-500">· {catalog.categories[it.category]?.label ?? it.category}</span></p>
            <p className="text-xs text-stone-500">{specLine(it.specs)} · from {it.source}</p>
            {it.missing_specs.length > 0 && <p className="text-xs text-red-700">Missing details: {it.missing_specs.join(", ")}. Not used in recommendations until added.</p>}
            {!it.usable && it.missing_specs.length === 0 && <p className="text-xs text-red-700">Marked suspect: excluded from builds.</p>}
          </div>
          <ConditionBadge condition={it.condition} />
          <input className="input w-20" type="number" min={1} defaultValue={it.quantity} aria-label="Quantity"
            onBlur={(e) => { const q = Math.max(1, Number(e.target.value) || 1); if (q !== it.quantity) run(() => api.patchItem(it.id, { quantity: q })); }} />
          <select className="input w-44" value={it.condition} aria-label="Condition"
            onChange={(e) => run(() => api.patchItem(it.id, { condition: e.target.value as Condition }))}>
            {catalog.conditions.map((c) => <option key={c} value={c}>{conditionLabel(c)}</option>)}
          </select>
          <button className="btn-danger" onClick={() => confirm(`Remove ${it.label}?`) && run(() => api.deleteItem(it.id))}>Remove</button>
        </div>
      ))}
    </div>
  );
}

import { useEffect, useState } from "react";
import { api } from "../api";
import type { Listing, ListingSuggestion } from "../types";
import { rupees } from "./format";
import { IconCheck, IconTag } from "./Icons";
import { ConditionBadge, errText, ErrorBanner, specLine } from "./ui";

/** Prefilled "list it for sale" form. Eligibility and the starting price come from code, not from the AI. */
export default function ListingAssistant({ itemId, onListed, onClose }: {
  itemId: number; onListed: (l: Listing) => void; onClose?: () => void;
}) {
  const [sug, setSug] = useState<ListingSuggestion | null>(null);
  const [title, setTitle] = useState("");
  const [qty, setQty] = useState(1);
  const [price, setPrice] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Listing | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setSug(null); setDone(null); setError(null);
    api.suggestListing(itemId).then((s) => {
      if (!live) return;
      setSug(s); setTitle(s.suggested_title); setQty(Math.max(1, s.suggested_quantity));
      setPrice((s.suggested_price_cents / 100).toString());
    }).catch((e) => live && setError(errText(e)));
    return () => { live = false; };
  }, [itemId]);

  if (error && !sug) return <ErrorBanner message={error} />;
  if (!sug) return <p className="text-sm text-stone-500">Preparing your listing…</p>;

  if (done) {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
        <IconCheck className="mt-0.5 shrink-0" />
        <div>
          <p className="font-medium">Listed: {done.quantity} × {done.label} at {rupees(done.price_cents)} each.</p>
          <p className="text-xs">Buyers see it as untested until they test it themselves. Manage it under Marketplace.</p>
        </div>
      </div>
    );
  }

  const cents = Math.round(Number(price) * 100);
  const valid = Number.isFinite(cents) && cents >= 1 && qty >= 1 && qty <= sug.quantity_owned && title.trim().length > 0;

  const list = async () => {
    setBusy(true); setError(null);
    try {
      const l = await api.createListing(sug.item_id, qty, cents, title.trim());
      setDone(l); onListed(l);
    } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-3 rounded-xl border border-stone-200 bg-stone-50 p-3">
      <div className="flex items-center gap-2 text-sm font-medium text-stone-800"><IconTag size={16} /> Sell this part</div>
      {!sug.can_list && <p role="alert" className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">{sug.problem} You can fix this under My parts.</p>}
      <ErrorBanner message={error} />

      <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
        <label className="text-sm">Listing name
          <input className="input mt-1" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} disabled={!sug.can_list} />
        </label>
        <label className="text-sm">Quantity
          <input className="input mt-1 w-24" type="number" min={1} max={sug.quantity_owned} value={qty}
            onChange={(e) => setQty(Math.min(sug.quantity_owned, Math.max(1, Number(e.target.value) || 1)))} disabled={!sug.can_list} />
          <span className="text-xs text-stone-500">of {sug.quantity_owned}</span>
        </label>
        <label className="text-sm">Price each (₹)
          <input className="input mt-1 w-28" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} disabled={!sug.can_list} />
          <span className="text-xs text-stone-500 tnum">Range {rupees(sug.price_low_cents)}–{rupees(sug.price_high_cents)}</span>
        </label>
      </div>
      <p className="text-xs text-stone-500">{sug.price_basis} It’s only a starting point; set your own price.</p>

      <div className="rounded-lg border border-dashed border-stone-300 bg-white p-3 text-sm">
        <p className="mb-1 text-xs text-stone-500">How buyers will see it</p>
        <p className="font-medium">{title || sug.label}</p>
        <p className="text-xs text-stone-500">{specLine(sug.specs)} · {qty} available</p>
        <div className="mt-1 flex items-center gap-2"><ConditionBadge condition={sug.condition} /><span className="tnum font-medium">{valid ? rupees(cents) : "—"}</span></div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button className="btn-primary" disabled={!sug.can_list || !valid || busy} onClick={list}>{busy ? "Listing…" : "List on marketplace"}</button>
        {onClose && <button className="btn-ghost" onClick={onClose}>Not now</button>}
      </div>
      <p className="text-xs text-stone-500">Marketplace: no real money moves. Listed parts leave your stock until sold or cancelled.</p>
    </div>
  );
}

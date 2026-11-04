import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { useCart } from "../cart/CartContext";
import { errText, ErrorBanner, money, Notice, specLine } from "../components/ui";
import type { ProjectMatch, ProjectOffers, Recommendations } from "../types";

const stars = (n: number) => "●".repeat(n) + "○".repeat(3 - n);

export default function Recommend({ onStarted }: { onStarted: () => void; onChanged?: () => void }) {
  const [data, setData] = useState<Recommendations | null>(null);
  const [offers, setOffers] = useState<Record<string, ProjectOffers>>({});
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [incomplete, setIncomplete] = useState<string | null>(null);
  const cart = useCart();

  const load = useCallback(async () => {
    try { setData(await api.recommendations()); setError(null); } catch (e) { setError(errText(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const start = async (slug: string, allow = false) => {
    setError(null);
    try { await api.startBuild(slug, allow); onStarted(); }
    catch (e) { if (e instanceof ApiError && e.status === 409) setIncomplete(slug); setError(errText(e)); }
  };
  const findParts = async (slug: string) => {
    try { const o = await api.offersFor(slug); setOffers((m) => ({ ...m, [slug]: o })); } catch (e) { setError(errText(e)); }
  };
  const addToCart = (label: string, listingId: number) => {
    cart.add(listingId, 1);
    setNote(`Added 1 × ${label} to your cart. Check out from the cart to get it.`);
  };

  if (!data) return <><ErrorBanner message={error} /><p className="text-sm text-stone-500">Loading…</p></>;
  const buildable = data.matches.filter((m) => m.can_build);
  const rest = data.matches.filter((m) => !m.can_build);

  const card = (m: ProjectMatch) => (
    <div key={m.slug} className="card space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">{m.title}</h3>
        <span className={`badge ${m.can_build ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-700"}`}>
          {m.can_build ? "You can build this now" : `${Math.round(m.coverage * 100)}% of parts`}
        </span>
        <span className="text-xs text-stone-500" title="Difficulty">{stars(m.difficulty)} · ~{m.estimated_minutes} min</span>
      </div>
      <p className="text-sm text-stone-600">{m.description}</p>
      <div className="h-1.5 overflow-hidden rounded bg-stone-100"><div className="h-full bg-emerald-600" style={{ width: `${m.coverage * 100}%` }} /></div>
      <ul className="space-y-0.5 text-sm">
        {m.requirements.map((r) => (
          <li key={r.index} className={r.status === "ok" ? "text-stone-700" : r.status === "partial" ? "text-amber-700" : "text-red-700"}>
            {r.status === "ok" ? "✓" : r.status === "partial" ? "◐" : "✗"} {r.needed} x {r.label}
            {r.allocated.length > 0 && <span className="text-stone-500"> — using {r.allocated.map((a) => `${a.quantity} x ${a.label}`).join(", ")}</span>}
            {r.missing > 0 && <span> — missing {r.missing}</span>}
          </li>
        ))}
      </ul>
      {m.requirements.some((r) => r.warnings.length > 0) && (
        <p className="text-xs text-amber-800">Some parts are untested. Test them before you rely on them.</p>
      )}
      {m.warnings.map((w, i) => <p key={i} className="text-xs text-stone-600">⚠ {w}</p>)}
      <div className="flex flex-wrap gap-2">
        {m.can_build
          ? <button className="btn-primary" onClick={() => start(m.slug)}>Start guided build</button>
          : <>
              <button className="btn-ghost" onClick={() => findParts(m.slug)}>Find missing parts</button>
              {incomplete === m.slug && <button className="btn-ghost" onClick={() => start(m.slug, true)}>Start anyway</button>}
              <button className="btn-ghost" onClick={() => start(m.slug)}>Start</button>
            </>}
      </div>
      {offers[m.slug] && (
        <div className="space-y-2 rounded-lg bg-stone-50 p-3">
          {offers[m.slug].parts.map((p) => (
            <div key={p.label}>
              <p className="text-sm font-medium">{p.quantity} x {p.label}</p>
              {p.offers.length === 0 && <p className="text-xs text-stone-500">No matching listings yet.</p>}
              {p.offers.map((l) => (
                <div key={l.id} className="mt-1 flex flex-wrap items-center gap-2 text-sm">
                  <span>{l.label} <span className="text-stone-500">({specLine(l.specs)}) · {l.quantity} left · {l.seller_name}</span></span>
                  <span className="font-medium">{money(l.price_cents)}</span>
                  <button className="btn-primary !py-1" onClick={() => addToCart(l.label, l.id)}>Add to cart</button>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-4">
      <ErrorBanner message={error} />
      {note && <div className="flex flex-wrap items-center gap-3"><Notice>{note}</Notice><button className="btn-ghost" onClick={cart.openCart}>View cart ({cart.count})</button></div>}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Build now ({buildable.length})</h2>
        {buildable.length === 0 && <p className="text-sm text-stone-600">Nothing is fully buildable yet. See what is closest below.</p>}
        {buildable.map(card)}
      </section>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Almost there</h2>
        {rest.map(card)}
      </section>
      {data.excluded_items.length > 0 && (
        <section className="card">
          <h3 className="mb-1 text-sm font-semibold">Parts not used in recommendations</h3>
          <ul className="space-y-0.5 text-sm text-stone-600">
            {data.excluded_items.map((x) => <li key={x.id}>{x.label}: {x.reason}</li>)}
          </ul>
        </section>
      )}
    </div>
  );
}

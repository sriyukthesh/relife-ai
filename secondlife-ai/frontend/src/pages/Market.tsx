import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useCart } from "../cart/CartContext";
import ListingAssistant from "../components/ListingAssistant";
import { errText, ErrorBanner, money, Notice, specLine } from "../components/ui";
import type { InventoryItem, Listing, Order } from "../types";

export default function Market({ onChanged }: { onChanged: () => void }) {
  const [browse, setBrowse] = useState<Listing[]>([]);
  const [mine, setMine] = useState<Listing[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [stock, setStock] = useState<InventoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [itemId, setItemId] = useState<number | "">("");
  const cart = useCart();

  const load = useCallback(async () => {
    try {
      const [b, m, o, s] = await Promise.all([api.listings(false), api.listings(true), api.orders(), api.inventory()]);
      setBrowse(b); setMine(m); setOrders(o); setStock(s.filter((x) => x.usable));
    } catch (e) { setError(errText(e)); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const run = async (fn: () => Promise<void>) => { setError(null); try { await fn(); await load(); onChanged(); } catch (e) { setError(errText(e)); await load(); } };

  return (
    <div className="space-y-5">
      <h1 className="page-title">Marketplace</h1>
      <Notice>Marketplace: add parts to your cart, then check out. Bought parts arrive as “not tested”, so test them before use.</Notice>
      <ErrorBanner message={error} />
      {note && <div className="flex flex-wrap items-center gap-3"><Notice>{note}</Notice>{cart.count > 0 && <button className="btn-ghost" onClick={cart.openCart}>View cart ({cart.count})</button>}</div>}

      <section className="space-y-2">
        <h2 className="font-display text-xl font-bold">Parts for sale</h2>
        {browse.length === 0 && <p className="text-sm text-stone-600">No listings from other makers right now.</p>}
        {browse.map((l) => (
          <div key={l.id} className="card flex flex-wrap items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{l.label}</p>
              <p className="text-xs text-stone-500">{specLine(l.specs)} · {l.quantity} left · {l.seller_name}{l.condition === "tested_ok" ? " · seller says tested" : ""}</p>
            </div>
            <span className="font-medium">{money(l.price_cents)}</span>
            <button className="btn-primary" onClick={() => { cart.add(l.id, 1); setNote(`Added 1 × ${l.label} to your cart.`); }}>Add to cart</button>
          </div>
        ))}
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-xl font-bold">Sell a part</h2>
        <div className="card space-y-3">
          <label className="block text-sm">Part to sell
            <select className="input mt-1 max-w-sm" value={itemId} onChange={(e) => setItemId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Choose…</option>
              {stock.map((s) => <option key={s.id} value={s.id}>{s.label} (x{s.quantity})</option>)}
            </select>
          </label>
          {itemId !== "" && <ListingAssistant key={itemId} itemId={itemId} onListed={(l) => { setNote(`Listed ${l.quantity} × ${l.label}. Buyers see it as untested until they test it.`); setItemId(""); load(); onChanged(); }} onClose={() => setItemId("")} />}
        </div>
        <p className="text-xs text-stone-500">Only parts with complete details that are not marked suspect can be listed. Listed parts leave your inventory until sold or cancelled.</p>
        {mine.map((l) => (
          <div key={l.id} className="card flex flex-wrap items-center gap-3">
            <span className="flex-1">{l.label} · {l.quantity} listed · {money(l.price_cents)}</span>
            <button className="btn-danger" onClick={() => run(() => api.cancelListing(l.id))}>Cancel</button>
          </div>
        ))}
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-xl font-bold">My orders</h2>
        <p className="text-xs text-stone-500">Full receipts are in your cart page under “Your orders”.</p>
        {orders.length === 0 && <p className="text-sm text-stone-600">No orders yet.</p>}
        {orders.map((o) => <div key={o.id} className="card text-sm">{o.quantity} x {o.label} · {money(o.total_cents)} · {new Date(o.created_at).toLocaleDateString()}</div>)}
      </section>
    </div>
  );
}

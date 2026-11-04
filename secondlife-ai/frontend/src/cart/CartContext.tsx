import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { CartLine } from "../types";

interface CartApi {
  lines: CartLine[];
  count: number;
  add: (listingId: number, qty?: number) => void;
  setQty: (listingId: number, qty: number) => void;
  remove: (listingId: number) => void;
  clear: () => void;
  openCart: () => void;
}

const Ctx = createContext<CartApi | null>(null);

function load(key: string): CartLine[] {
  try {
    const raw = JSON.parse(localStorage.getItem(key) ?? "[]");
    if (!Array.isArray(raw)) return [];
    return raw
      .filter((l) => l && Number.isInteger(l.listing_id) && Number.isInteger(l.quantity) && l.quantity > 0)
      .map((l) => ({ listing_id: l.listing_id, quantity: Math.min(l.quantity, 10000) }));
  } catch { return []; }
}

/** Cart kept on this device per user. Prices and availability always come from the server. */
export function CartProvider({ userId, onOpenCart, children }: { userId: number; onOpenCart: () => void; children: ReactNode }) {
  const key = `sl-cart-${userId}`;
  const [lines, setLines] = useState<CartLine[]>(() => load(key));
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(lines)); } catch { /* private mode */ } }, [lines, key]);

  const add = useCallback((id: number, qty = 1) => setLines((ls) =>
    ls.some((l) => l.listing_id === id)
      ? ls.map((l) => (l.listing_id === id ? { ...l, quantity: Math.min(10000, l.quantity + qty) } : l))
      : [...ls, { listing_id: id, quantity: qty }]), []);
  const setQty = useCallback((id: number, qty: number) =>
    setLines((ls) => ls.map((l) => (l.listing_id === id ? { ...l, quantity: Math.max(1, Math.min(10000, qty)) } : l))), []);
  const remove = useCallback((id: number) => setLines((ls) => ls.filter((l) => l.listing_id !== id)), []);
  const clear = useCallback(() => setLines([]), []);

  const value = useMemo<CartApi>(() => ({
    lines, count: lines.reduce((n, l) => n + l.quantity, 0), add, setQty, remove, clear, openCart: onOpenCart,
  }), [lines, add, setQty, remove, clear, onOpenCart]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCart(): CartApi {
  const c = useContext(Ctx);
  if (!c) throw new Error("useCart must be used inside CartProvider");
  return c;
}

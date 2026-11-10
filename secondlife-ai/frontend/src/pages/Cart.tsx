import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError } from "../api";
import { useCart } from "../cart/CartContext";
import { IconCart, IconCheck, IconLock, IconTrash } from "../components/Icons";
import PayPalButtons from "../components/PayPalButtons";
import { ConditionBadge, errText, ErrorBanner, money, Notice, specLine } from "../components/ui";
import type { Tab } from "../nav";
import type { Address, CartPreview, Payment } from "../types";

type Step = "cart" | "address" | "payment" | "review" | "done";
const STEPS: { id: Step; label: string }[] = [
  { id: "cart", label: "Cart" }, { id: "address", label: "Delivery" }, { id: "payment", label: "PayPal" }, { id: "review", label: "Review & pay" },
];
const newKey = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `k${Date.now()}${Math.random().toString(16).slice(2)}`);
const EMPTY_ADDR: Address = { full_name: "", phone: "", line1: "", city: "", pincode: "" };

function Stepper({ step }: { step: Step }) {
  const idx = STEPS.findIndex((s) => s.id === step);
  return (
    <ol className="flex items-center gap-2 text-sm" aria-label="Checkout progress">
      {STEPS.map((s, i) => (
        <li key={s.id} className="flex items-center gap-2" aria-current={i === idx ? "step" : undefined}>
          <span className={`grid h-6 w-6 place-items-center rounded-full text-xs font-medium ${i < idx ? "bg-emerald-600 text-white" : i === idx ? "bg-ink text-white" : "bg-stone-200 text-stone-600"}`}>
            {i < idx ? <IconCheck size={14} /> : i + 1}
          </span>
          <span className={`hidden sm:inline ${i === idx ? "font-medium text-stone-900" : "text-stone-500"}`}>{s.label}</span>
          {i < STEPS.length - 1 && <span aria-hidden className="h-px w-5 bg-stone-300 sm:w-8" />}
        </li>
      ))}
    </ol>
  );
}

function Summary({ preview, cta }: { preview: CartPreview | null; cta: ReactNode }) {
  const items = preview?.lines.reduce((n, l) => n + (l.issue ? 0 : l.quantity), 0) ?? 0;
  const gap = preview ? Math.max(0, preview.free_delivery_from_cents - preview.subtotal_cents) : 0;
  const pct = preview && preview.free_delivery_from_cents ? Math.min(100, (preview.subtotal_cents / preview.free_delivery_from_cents) * 100) : 0;
  return (
    <aside className="h-fit space-y-3 border-t-2 border-ink pt-3 lg:sticky lg:top-6" aria-label="Order summary">
      <h2 className="font-display text-lg font-bold">Order summary</h2>
      <dl className="space-y-1.5 text-sm">
        <div className="flex justify-between"><dt className="text-stone-600">Items ({items})</dt><dd className="tnum">{money(preview?.subtotal_cents ?? 0)}</dd></div>
        <div className="flex justify-between"><dt className="text-stone-600">Delivery (demo)</dt><dd className="tnum">{preview && preview.subtotal_cents > 0 ? (preview.delivery_cents === 0 ? "Free" : money(preview.delivery_cents)) : "—"}</dd></div>
        <div className="flex justify-between border-t border-stone-200 pt-2 text-base font-semibold"><dt>Total</dt><dd className="tnum">{money(preview?.total_cents ?? 0)}</dd></div>
      </dl>
      {preview && preview.subtotal_cents > 0 && gap > 0 && (
        <div>
          <p className="text-xs text-stone-600">Add {money(gap)} more for free delivery</p>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-stone-200"><div className="h-full rounded-full bg-gold" style={{ width: `${pct}%` }} /></div>
        </div>
      )}
      {cta}
      <p className="flex items-center gap-1.5 text-xs text-stone-500"><IconLock size={13} /> Demo checkout. No real money is taken.</p>
    </aside>
  );
}

export default function Cart({ userId, userName, onNavigate, onChanged }: {
  userId: number; userName: string; onNavigate: (t: Tab) => void; onChanged: () => void;
}) {
  const cart = useCart();
  const [step, setStep] = useState<Step>("cart");
  const [preview, setPreview] = useState<CartPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addr, setAddr] = useState<Address>(() => {
    try { return { ...EMPTY_ADDR, ...JSON.parse(localStorage.getItem(`sl-addr-${userId}`) ?? "{}") }; } catch { return EMPTY_ADDR; }
  });
  const [addrErr, setAddrErr] = useState<Partial<Record<keyof Address, string>>>({});
  const [saveAddr, setSaveAddr] = useState(true);
  const [paying, setPaying] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [canRestartCheckout, setCanRestartCheckout] = useState(false);
  const [receipt, setReceipt] = useState<Payment | null>(null);
  const [history, setHistory] = useState<Payment[]>([]);
  const keyRef = useRef(newKey());

  useEffect(() => { setAddr((a) => (a.full_name ? a : { ...a, full_name: userName })); }, [userName]);

  const linesKey = JSON.stringify(cart.lines);
  const refresh = useCallback(async () => {
    if (cart.lines.length === 0) { setPreview(null); return; }
    setLoading(true);
    try { setPreview(await api.checkoutPreview(cart.lines)); setError(null); } catch (e) { setError(errText(e)); } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linesKey]);
  useEffect(() => { if (step !== "done") refresh(); }, [refresh, step]);

  const loadHistory = useCallback(() => { api.payments().then(setHistory).catch(() => setHistory([])); }, []);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  const lines = preview?.lines ?? [];
  const hasIssue = lines.some((l) => l.issue);
  const canProceed = Boolean(preview?.ok) && !loading;

  const validateAddr = (): boolean => {
    const e: Partial<Record<keyof Address, string>> = {};
    if (addr.full_name.trim().length < 2) e.full_name = "Enter the receiver’s name.";
    if (!/^\d{10}$/.test(addr.phone)) e.phone = "Enter a 10-digit mobile number.";
    if (addr.line1.trim().length < 5) e.line1 = "Enter house / street / area (at least 5 characters).";
    if (addr.city.trim().length < 2) e.city = "Enter the city.";
    if (!/^\d{6}$/.test(addr.pincode)) e.pincode = "Enter a 6-digit PIN code.";
    setAddrErr(e);
    return Object.keys(e).length === 0;
  };
  const finishPayment = useCallback((value: Payment) => {
    if (saveAddr) { try { localStorage.setItem(`sl-addr-${userId}`, JSON.stringify(addr)); } catch { /* ignore */ } }
    keyRef.current = newKey();
    setReceipt(value);
    setStep("done");
    cart.clear();
    onChanged();
    loadHistory();
  }, [addr, cart.clear, loadHistory, onChanged, saveAddr, userId]);

  const createPayPalOrder = useCallback(async () => {
    if (!preview?.ok) throw new Error("Please review your cart before paying.");
    const result = await api.createPayPalOrder({
      lines: preview.lines.map((line) => ({ listing_id: line.listing_id, quantity: line.quantity })),
      address: { ...addr, full_name: addr.full_name.trim(), line1: addr.line1.trim(), city: addr.city.trim() },
      idempotency_key: keyRef.current,
    });
    setCanRestartCheckout(false);
    return result.paypal_order_id;
  }, [addr, preview]);

  const capturePayPalOrder = useCallback(async (orderId: string) => {
    setPaying(true);
    setFailure(null);
    try {
      finishPayment(await api.capturePayPalOrder(orderId));
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        refresh();
        const detail = typeof e.detail === "string" ? e.detail : "";
        setCanRestartCheckout(detail.includes("Review your cart and start checkout again"));
      }
      setFailure(errText(e));
    } finally {
      setPaying(false);
    }
  }, [finishPayment, refresh]);

  const paypalError = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 409) setCanRestartCheckout(true);
    setFailure(errText(e));
  }, []);

  // ---------- success ----------
  if (step === "done" && receipt) {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="space-y-2 text-center">
          <div className="mx-auto grid h-16 w-16 animate-rise place-items-center rounded-full bg-emerald-600 text-white"><IconCheck size={34} /></div>
          <h1 className="page-title">Sandbox payment successful</h1>
          <p className="text-stone-700">{money(receipt.total_cents)} paid with {receipt.method_label}</p>
          <p className="text-sm text-stone-500">Order reference <span className="font-medium tnum text-stone-800">{receipt.reference}</span> · {new Date(receipt.created_at).toLocaleString()}</p>
        </div>
        <Notice>The parts are now in My parts, marked untested. This sandbox payment moved no real money, and nothing is shipped.</Notice>
        <section className="border-t-2 border-ink pt-3">
          <h2 className="mb-3 font-display text-lg font-bold">What you bought</h2>
          <ul className="divide-y divide-stone-200 text-sm">
            {receipt.lines.map((l) => (
              <li key={l.order_id} className="flex justify-between gap-3 py-2"><span>{l.quantity} × {l.label} <span className="text-stone-500">from {l.seller_name}</span></span><span className="tnum">{money(l.line_cents)}</span></li>
            ))}
          </ul>
          <dl className="mt-3 space-y-1 text-sm">
            <div className="flex justify-between"><dt className="text-stone-600">Items</dt><dd className="tnum">{money(receipt.subtotal_cents)}</dd></div>
            <div className="flex justify-between"><dt className="text-stone-600">Delivery (demo)</dt><dd className="tnum">{receipt.delivery_cents === 0 ? "Free" : money(receipt.delivery_cents)}</dd></div>
            <div className="flex justify-between border-t border-stone-200 pt-2 font-semibold"><dt>Total paid</dt><dd className="tnum">{money(receipt.total_cents)}</dd></div>
          </dl>
          <p className="mt-3 text-xs text-stone-500">Delivery address (demo): {receipt.address.full_name}, {receipt.address.line1}, {receipt.address.city} {receipt.address.pincode}</p>
        </section>
        <div className="flex flex-wrap justify-center gap-2">
          <button className="btn-primary" onClick={() => onNavigate("parts")}>View in My parts</button>
          <button className="btn-ghost" onClick={() => onNavigate("market")}>Keep shopping</button>
          <button className="btn-ghost" onClick={() => window.print()}>Print receipt</button>
        </div>
      </div>
    );
  }

  const stepIndex = STEPS.findIndex((s) => s.id === step);
  const cta =
    step === "cart" ? <button className="btn-primary w-full" disabled={!canProceed} onClick={() => setStep("address")}>Proceed to delivery</button>
    : step === "address" ? <button className="btn-primary w-full" onClick={() => validateAddr() && setStep("payment")}>Continue to payment</button>
    : step === "payment" ? <button className="btn-primary w-full" onClick={() => setStep("review")}>Review order</button>
    : <p className="text-sm text-stone-600">Use the PayPal button to complete your sandbox payment.</p>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="page-title">{step === "cart" ? "Your cart" : "Checkout"}</h1>
        {lines.length > 0 && <Stepper step={step} />}
      </div>
      <ErrorBanner message={error} />

      {cart.lines.length === 0 && step === "cart" ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-dashed border-stone-300 bg-white px-6 py-12 text-center">
            <IconCart size={32} className="mx-auto text-stone-400" />
            <p className="mt-3 font-medium">Your cart is empty</p>
            <p className="text-sm text-stone-600">Find parts from other makers in the marketplace.</p>
            <button className="btn-primary mt-4" onClick={() => onNavigate("market")}>Browse marketplace</button>
          </div>
          <OrderHistory items={history} />
        </div>
      ) : (
        <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
          <div className="space-y-5">
            {step === "cart" && (
              <>
                {hasIssue && (
                  <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                    <span className="flex-1">Some items changed since you added them. Fix or remove them to continue.</span>
                    <button className="btn-ghost !py-1" onClick={() => lines.filter((l) => l.issue && l.quantity_available === 0).forEach((l) => cart.remove(l.listing_id))}>Remove unavailable</button>
                  </div>
                )}
                <ul className="space-y-3">
                  {lines.map((l) => {
                    const q = cart.lines.find((c) => c.listing_id === l.listing_id)?.quantity ?? l.quantity;
                    return (
                    <li key={l.listing_id} className="card">
                      <div className="flex flex-wrap items-start gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="font-medium">{l.label}</p>
                          <p className="text-xs text-stone-500">{specLine(l.specs)} · sold by {l.seller_name}</p>
                          <div className="mt-1 flex items-center gap-2"><ConditionBadge condition={l.condition} /><span className="text-xs text-stone-500 tnum">{money(l.unit_cents)} each</span></div>
                          {l.issue && <p role="alert" className="mt-1 text-xs font-medium text-red-700">{l.issue}</p>}
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="inline-flex items-center rounded-lg border border-stone-300" role="group" aria-label={`Quantity of ${l.label}`}>
                            <button className="px-3 py-1.5 text-lg leading-none disabled:opacity-40" aria-label="Decrease quantity" disabled={q <= 1} onClick={() => cart.setQty(l.listing_id, q - 1)}>−</button>
                            <span className="min-w-8 text-center text-sm tnum">{q}</span>
                            <button className="px-3 py-1.5 text-lg leading-none disabled:opacity-40" aria-label="Increase quantity" disabled={l.quantity_available > 0 && q >= l.quantity_available} onClick={() => cart.setQty(l.listing_id, q + 1)}>+</button>
                          </div>
                          <span className="w-20 text-right font-medium tnum">{money(l.line_cents)}</span>
                          <button className="grid h-9 w-9 place-items-center rounded-full text-stone-500 hover:bg-stone-100 hover:text-red-700" aria-label={`Remove ${l.label}`} onClick={() => cart.remove(l.listing_id)}><IconTrash size={18} /></button>
                        </div>
                      </div>
                    </li>
                    );
                  })}
                </ul>
                {loading && <p className="text-xs text-stone-500">Updating prices…</p>}
                <OrderHistory items={history} />
              </>
            )}

            {step === "address" && (
              <section className="space-y-4">
                <h2 className="font-display text-xl font-bold">Delivery address</h2>
                <Notice>Demo only: any dummy address works. Nothing is shipped.</Notice>
                <div className="grid gap-4 sm:grid-cols-2">
                  {([
                    ["full_name", "Full name", "name", "sm:col-span-2"], ["phone", "Mobile number", "tel", ""], ["pincode", "PIN code", "postal-code", ""],
                    ["line1", "House no., street, area", "street-address", "sm:col-span-2"], ["city", "City", "address-level2", ""],
                  ] as [keyof Address, string, string, string][]).map(([k, label, ac, span]) => (
                    <label key={k} className={`text-sm ${span}`}>{label}
                      <input className={`input mt-1 ${addrErr[k] ? "!border-red-400" : ""}`} value={addr[k]} autoComplete={ac}
                        inputMode={k === "phone" || k === "pincode" ? "numeric" : undefined}
                        maxLength={k === "phone" ? 10 : k === "pincode" ? 6 : 120}
                        onChange={(e) => setAddr({ ...addr, [k]: k === "phone" || k === "pincode" ? e.target.value.replace(/\D/g, "") : e.target.value })} />
                      {addrErr[k] && <span role="alert" className="text-xs text-red-700">{addrErr[k]}</span>}
                    </label>
                  ))}
                </div>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={saveAddr} onChange={(e) => setSaveAddr(e.target.checked)} /> Save this address on this device</label>
                <button className="btn-ghost" onClick={() => { keyRef.current = newKey(); setStep("cart"); }}>← Back to cart</button>
              </section>
            )}

            {step === "payment" && (
              <section className="space-y-4">
                <h2 className="font-display text-xl font-bold">PayPal sandbox</h2>
                <Notice>PayPal handles the payment details. You will approve this order in PayPal’s sandbox; no live money is used.</Notice>
                <button className="btn-ghost" onClick={() => { keyRef.current = newKey(); setStep("address"); }}>← Back to delivery</button>
              </section>
            )}

            {step === "review" && (
              <section className="space-y-5">
                <h2 className="font-display text-xl font-bold">Review your order</h2>
                {failure && (
                  <div role="alert" className="space-y-2 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">
                    <p className="font-medium">Payment failed</p><p>{failure}</p>
                    <div className="flex flex-wrap gap-2">
                      <button className="btn-ghost !py-1" onClick={() => setFailure(null)}>Try PayPal again</button>
                      {canRestartCheckout && <button className="btn-ghost !py-1" onClick={() => { keyRef.current = newKey(); setFailure(null); setCanRestartCheckout(false); setStep("cart"); }}>Review cart</button>}
                    </div>
                  </div>
                )}
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="card text-sm">
                    <div className="flex justify-between"><h3 className="font-semibold">Deliver to</h3><button className="text-xs underline" onClick={() => { keyRef.current = newKey(); setStep("address"); }}>Change</button></div>
                    <p className="mt-1">{addr.full_name}</p><p className="text-stone-600">{addr.line1}, {addr.city} {addr.pincode}</p><p className="text-stone-600">Mobile {addr.phone}</p>
                  </div>
                  <div className="card text-sm">
                    <h3 className="font-semibold">Pay with</h3>
                    <p className="mt-1">PayPal sandbox</p>
                  </div>
                </div>
                <ul className="divide-y divide-stone-200 rounded-xl border border-stone-200 bg-white text-sm">
                  {lines.map((l) => (
                    <li key={l.listing_id} className="flex justify-between gap-3 px-4 py-2.5"><span>{l.quantity} × {l.label} <span className="text-stone-500">· {l.seller_name}</span></span><span className="tnum">{money(l.line_cents)}</span></li>
                  ))}
                </ul>
                <p className="text-xs text-stone-500">Parts arrive in My parts marked untested. Please test them before use.</p>
                  <PayPalButtons onCreateOrder={createPayPalOrder} onApprove={capturePayPalOrder} onError={paypalError} />
                  <button className="btn-ghost" onClick={() => setStep("payment")}>← Back to payment</button>
              </section>
            )}
          </div>

          <Summary preview={preview} cta={cta} />
        </div>
      )}

      {paying && (
        <div className="fixed inset-0 z-[60] grid place-items-center bg-ink/80 px-6" role="alertdialog" aria-live="assertive" aria-label="Processing payment">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 text-center">
            <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-stone-200 border-t-emerald-600" />
            <p className="mt-4 font-display text-lg font-bold">Processing {money(preview?.total_cents ?? 0)}</p>
            <p className="mt-1 text-sm text-stone-600">Confirming your PayPal sandbox payment and adding the parts to your account…</p>
            <p className="mt-3 text-xs text-stone-500">Please don’t close or refresh this page.</p>
          </div>
        </div>
      )}
      <span className="sr-only" aria-live="polite">{`Step ${stepIndex + 1} of ${STEPS.length}`}</span>
    </div>
  );
}

function OrderHistory({ items }: { items: Payment[] }) {
  if (items.length === 0) return null;
  return (
    <section className="border-t-2 border-ink pt-3">
      <h2 className="mb-3 font-display text-lg font-bold">Your orders</h2>
      <ul className="space-y-2">
        {items.map((p) => (
          <li key={p.id}>
            <details className="card text-sm">
              <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-2">
                <span><span className="font-medium tnum">{p.reference}</span> <span className="text-stone-500">· {new Date(p.created_at).toLocaleDateString()}</span></span>
                <span className="tnum font-medium">{money(p.total_cents)} <span className="badge bg-emerald-100 text-emerald-800">Paid</span></span>
              </summary>
              <ul className="mt-2 space-y-1 text-stone-700">{p.lines.map((l) => <li key={l.order_id} className="flex justify-between"><span>{l.quantity} × {l.label}</span><span className="tnum">{money(l.line_cents)}</span></li>)}</ul>
              <p className="mt-2 text-xs text-stone-500">{p.method_label}{p.delivery_cents ? ` · delivery ${money(p.delivery_cents)}` : " · free delivery"}</p>
            </details>
          </li>
        ))}
      </ul>
    </section>
  );
}

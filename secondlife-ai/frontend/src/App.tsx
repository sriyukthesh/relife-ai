import { lazy, Suspense, useEffect, useState } from "react";
import { api, hasToken, setToken } from "./api";
import CopilotPanel from "./components/CopilotPanel";
import { CartProvider, useCart } from "./cart/CartContext";
import { BrandMark, IconBack, IconCart, IconLogout } from "./components/Icons";
import { errText, ErrorBanner } from "./components/ui";
import { NAV, type Tab } from "./nav";
import Build from "./pages/Build";
import Cart from "./pages/Cart";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Market from "./pages/Market";
import Parts from "./pages/Parts";
import Recommend from "./pages/Recommend";
import Scan from "./pages/Scan";
import Workbench from "./pages/Workbench";
import type { Catalog, User } from "./types";
import type { ListingRow } from "./grid/dataSources";

const DataGrids = lazy(() => import("./pages/DataGrids"));
const Timeline = lazy(() => import("./pages/Timeline"));

function DataGridsPage({ refreshKey }: { refreshKey: number }) {
  const cart = useCart();
  const addToCart = (listing: ListingRow) => cart.add(listing.id, 1);
  return (
    <Suspense fallback={<p className="text-sm text-stone-500">Loading data tables…</p>}>
      <DataGrids refreshKey={refreshKey} onAddToCart={addToCart} />
    </Suspense>
  );
}

function CartButton({ onClick, active, className = "", label }: { onClick: () => void; active?: boolean; className?: string; label?: string }) {
  const { count } = useCart();
  return (
    <button onClick={onClick} aria-label={`Cart, ${count} item${count === 1 ? "" : "s"}`} aria-current={active ? "page" : undefined} className={className}>
      <span className="relative inline-flex"><IconCart size={18} />
        {count > 0 && <span className="absolute -right-2 -top-2 grid h-4 min-w-4 place-items-center rounded-full bg-gold px-1 text-[10px] font-semibold leading-none text-white tnum">{count > 99 ? "99+" : count}</span>}
      </span>
      {label}
    </button>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [tab, setTab] = useState<Tab>("dashboard");
  const [tabHistory, setTabHistory] = useState<Tab[]>(["dashboard"]);
  const [checking, setChecking] = useState(hasToken());
  const [error, setError] = useState<string | null>(null);
  const [partsKey, setPartsKey] = useState(0);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const bump = () => setPartsKey((k) => k + 1);

  useEffect(() => {
    if (!hasToken()) return;
    api.me().then(setUser).catch(() => setToken(null)).finally(() => setChecking(false));
  }, []);
  useEffect(() => {
    if (user) api.catalog().then(setCatalog).catch((e) => setError(errText(e)));
  }, [user]);

  const logout = () => { setToken(null); setUser(null); setCopilotOpen(false); setTab("dashboard"); setTabHistory(["dashboard"]); };
  const go = (t: Tab) => {
    if (t !== tab) {
      setTab(t);
      setTabHistory((history) => [...history, t]);
      window.scrollTo({ top: 0 });
    }
  };
  const goBack = () => {
    if (tabHistory.length < 2) return;
    const previous = tabHistory[tabHistory.length - 2];
    setTab(previous);
    setTabHistory((history) => history.slice(0, -1));
    window.scrollTo({ top: 0 });
  };

  if (checking) return <p className="p-6 text-sm text-stone-500">Loading…</p>;
  if (!user) return <Login onLogin={(u) => { setUser(u); setTab("dashboard"); setTabHistory(["dashboard"]); }} />;

  const openCopilot = () => setCopilotOpen(true);
  const wide = tab === "dashboard" || tab === "cart" || tab === "grids" || tab === "timeline";

  return (
    <CartProvider userId={user.id} onOpenCart={() => go("cart")}>
    <div className="min-h-screen lg:pl-60">
      {/* Desktop rail */}
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col bg-ink text-emerald-50 lg:flex">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <BrandMark />
          <span className="font-display text-lg font-bold text-white">ReLife AI</span>
        </div>
        <nav className="flex-1 space-y-0.5 px-3" aria-label="Main">
          {NAV.map(({ tab: t, label, Icon }) => (
            <button key={t} onClick={() => go(t)} aria-current={tab === t ? "page" : undefined}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition ${tab === t ? "bg-white/10 font-medium text-white" : "text-emerald-100/80 hover:bg-white/5"}`}>
              <Icon size={18} className={tab === t ? "text-gold-soft" : ""} /> {label}
            </button>
          ))}
          <div className="my-2 border-t border-white/10" />
          <CartButton onClick={() => go("cart")} active={tab === "cart"} label="Cart"
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition ${tab === "cart" ? "bg-white/10 font-medium text-white" : "text-emerald-100/80 hover:bg-white/5"}`} />
        </nav>
        <div className="border-t border-white/10 px-5 py-4 text-sm">
          <p className="truncate font-medium text-white">{user.name}</p>
          <p className="truncate text-xs text-emerald-100/70">{user.email}</p>
          <button onClick={logout} className="mt-2 flex items-center gap-1.5 text-xs text-emerald-100/80 hover:text-white"><IconLogout size={14} /> Log out</button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between bg-ink px-4 py-3 text-white lg:hidden">
        <div className="flex items-center gap-2"><BrandMark size={24} /><span className="font-display font-bold">ReLife AI</span></div>
        <div className="flex items-center gap-4">
          <CartButton onClick={() => go("cart")} active={tab === "cart"} className="grid h-9 w-9 place-items-center rounded-full text-white hover:bg-white/10" />
          <button onClick={logout} className="flex items-center gap-1 text-xs text-emerald-100/80"><IconLogout size={14} /> Log out</button>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 pb-28 pt-6 sm:px-6 lg:px-8 lg:pb-16 lg:pt-8">
        <ErrorBanner message={error} />
        {!catalog ? <p className="text-sm text-stone-500">Loading…</p> : (
          <main>
            {tabHistory.length > 1 && (
              <button onClick={goBack} className="mb-4 inline-flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium text-stone-600 transition hover:bg-stone-100 hover:text-stone-900">
                <IconBack size={18} /> Back
              </button>
            )}
            {tab === "dashboard" && <Dashboard user={user} onNavigate={go} onOpenCopilot={openCopilot} />}
            {tab === "cart" && <Cart userId={user.id} userName={user.name} onNavigate={go} onChanged={bump} />}
            <div className={wide ? "hidden" : "mx-auto max-w-3xl"}>
              {tab === "scan" && <Scan catalog={catalog} onAdded={bump} />}
              {tab === "parts" && <Parts catalog={catalog} refreshKey={partsKey} />}
              {tab === "recommend" && <Recommend key={partsKey} onStarted={() => go("build")} onChanged={bump} />}
              {tab === "build" && <Build onGoRecommend={() => go("recommend")} onOpenCopilot={openCopilot} />}
              {tab === "workbench" && <Workbench catalog={catalog} onChanged={bump} />}
              {tab === "market" && <Market onChanged={bump} />}
            </div>
            {tab === "grids" && <DataGridsPage refreshKey={partsKey} />}
            {tab === "timeline" && (
              <Suspense fallback={<p className="text-sm text-stone-500">Loading project timeline…</p>}>
                <Timeline />
              </Suspense>
            )}
          </main>
        )}
        <footer className="mt-12 text-center text-xs text-stone-500">
          You confirm, code decides. Verify parts with a multimeter before connecting power.
        </footer>
      </div>

      {/* Mobile bottom tabs */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-9 border-t border-stone-200 bg-white pb-[env(safe-area-inset-bottom)] lg:hidden">
        {NAV.map(({ tab: t, short, Icon }) => (
          <button key={t} onClick={() => go(t)} aria-current={tab === t ? "page" : undefined}
            className={`flex flex-col items-center gap-0.5 py-2 text-[11px] ${tab === t ? "font-medium text-emerald-700" : "text-stone-500"}`}>
            <Icon size={20} /> {short}
          </button>
        ))}
      </nav>

      {/* Always available after login */}
      <CopilotPanel open={copilotOpen} onOpen={openCopilot} onClose={() => setCopilotOpen(false)} userName={user.name} />
    </div>
    </CartProvider>
  );
}

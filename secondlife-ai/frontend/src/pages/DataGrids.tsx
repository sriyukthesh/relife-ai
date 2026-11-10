import { useState } from "react";
import InventoryGrid from "../grid/InventoryGrid";
import MarketGrid from "../grid/MarketGrid";
import OrdersGrid from "../grid/OrdersGrid";
import type { ListingRow } from "../grid/dataSources";

type View = "parts" | "market" | "orders";
const VIEWS: [View, string][] = [["parts", "My parts"], ["market", "Marketplace"], ["orders", "Orders"]];

/**
 * Data tables page. Wire it into the app as a tab/route.
 * Pass onAddToCart (your existing cart function) to enable the cart button in the marketplace table.
 */
export default function DataGrids({
  onAddToCart, refreshKey = 0,
}: { onAddToCart?: (listing: ListingRow) => void; refreshKey?: number }) {
  const [view, setView] = useState<View>("parts");
  return (
    <div className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold">Data tables</h2>
        <p className="text-sm text-stone-600">Sort, filter, search, edit and export your data.</p>
      </div>
      <div className="flex gap-1">
        {VIEWS.map(([k, label]) => (
          <button key={k} onClick={() => setView(k)}
            className={`rounded-lg px-4 py-2 text-sm font-medium ${view === k ? "bg-emerald-700 text-white" : "border border-stone-300 bg-white hover:bg-stone-100"}`}>
            {label}
          </button>
        ))}
      </div>
      {view === "parts" && <InventoryGrid refreshKey={refreshKey} />}
      {view === "market" && <MarketGrid onAddToCart={onAddToCart} refreshKey={refreshKey} />}
      {view === "orders" && <OrdersGrid refreshKey={refreshKey} />}
    </div>
  );
}

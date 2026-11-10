import { useCallback, useEffect, useMemo, useState } from "react";
import type { ColDef } from "ag-grid-community";
import GridShell from "./GridShell";
import { ActionCell, type ActionContext } from "./cells";
import { fetchListings, type ListingRow } from "./dataSources";
import { moneyFromCents, specsText, titleCase } from "./format";

/**
 * Parts for sale from other makers. Pass `onAddToCart` to show a cart button; the app decides
 * what happens next (cart, PayPal sandbox checkout, etc.). Without it the grid is browse-only.
 */
export default function MarketGrid({
  onAddToCart, refreshKey = 0,
}: { onAddToCart?: (listing: ListingRow) => void; refreshKey?: number }) {
  const [rows, setRows] = useState<ListingRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setRows(await fetchListings()); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load listings"); setRows([]); }
  }, []);
  useEffect(() => { load(); }, [load, refreshKey]);

  const columnDefs = useMemo<ColDef<ListingRow>[]>(() => {
    const cols: ColDef<ListingRow>[] = [
      { field: "label", headerName: "Part", minWidth: 170, filter: "agTextColumnFilter" },
      { field: "category", headerName: "Type", valueFormatter: (p) => titleCase(p.value), filter: "agTextColumnFilter" },
      { headerName: "Details", valueGetter: (p) => specsText(p.data?.specs), minWidth: 220, flex: 2, filter: "agTextColumnFilter" },
      { field: "seller_name", headerName: "Seller", filter: "agTextColumnFilter" },
      { field: "condition", headerName: "Seller says",
        valueFormatter: (p) => (p.value === "tested_ok" ? "Tested" : "Not tested"), filter: "agTextColumnFilter", maxWidth: 140 },
      { field: "quantity", headerName: "Available", filter: "agNumberColumnFilter", maxWidth: 130 },
      { field: "price_cents", headerName: "Price each", sort: "asc", filter: "agNumberColumnFilter",
        valueFormatter: (p) => moneyFromCents(p.value), maxWidth: 150 },
    ];
    if (onAddToCart) cols.push({ headerName: "", colId: "action", cellRenderer: ActionCell, sortable: false, filter: false,
      floatingFilter: false, minWidth: 140, maxWidth: 160, flex: 0 });
    return cols;
  }, [onAddToCart]);

  const context = useMemo<ActionContext<ListingRow>>(() => ({ onAction: onAddToCart, actionLabel: "Add to cart" }), [onAddToCart]);

  return (
    <GridShell<ListingRow>
      gridId="market" exportName="relife-marketplace" rowData={rows} columnDefs={columnDefs}
      getRowId={(p) => String(p.data.id)} error={error} onRefresh={load} context={context}
      emptyMessage="No listings from other makers right now."
    />
  );
}

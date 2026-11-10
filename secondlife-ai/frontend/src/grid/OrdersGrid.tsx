import { useCallback, useEffect, useMemo, useState } from "react";
import type { ColDef } from "ag-grid-community";
import GridShell from "./GridShell";
import { fetchOrders, type OrderRow } from "./dataSources";
import { moneyFromCents, shortDate, titleCase } from "./format";

/** Order history with a pinned totals row and CSV export. */
export default function OrdersGrid({ refreshKey = 0 }: { refreshKey?: number }) {
  const [rows, setRows] = useState<OrderRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setRows(await fetchOrders()); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load orders"); setRows([]); }
  }, []);
  useEffect(() => { load(); }, [load, refreshKey]);

  const columnDefs = useMemo<ColDef<OrderRow>[]>(() => [
    { field: "id", headerName: "Order #", maxWidth: 120, filter: "agNumberColumnFilter",
      valueFormatter: (p) => (p.node?.rowPinned ? "" : `#${p.value}`) },
    { field: "created_at", headerName: "Date", sort: "desc", valueFormatter: (p) => shortDate(p.value), filter: "agDateColumnFilter",
      filterValueGetter: (p) => (p.data ? new Date(p.data.created_at) : null) },
    { field: "label", headerName: "Part", minWidth: 180, flex: 2, filter: "agTextColumnFilter" },
    { field: "quantity", headerName: "Qty", maxWidth: 110, filter: "agNumberColumnFilter" },
    { field: "total_cents", headerName: "Total", valueFormatter: (p) => moneyFromCents(p.value), filter: "agNumberColumnFilter" },
    { field: "status", headerName: "Status", valueFormatter: (p) => titleCase(p.value), filter: "agTextColumnFilter", maxWidth: 150 },
  ], []);

  const totals = useMemo<Partial<OrderRow>[]>(() => {
    if (!rows || rows.length === 0) return [];
    return [{ label: "Total", quantity: rows.reduce((s, r) => s + r.quantity, 0), total_cents: rows.reduce((s, r) => s + r.total_cents, 0) }];
  }, [rows]);

  return (
    <GridShell<OrderRow>
      gridId="orders" exportName="relife-orders" rowData={rows} columnDefs={columnDefs}
      getRowId={(p) => String(p.data.id)} error={error} onRefresh={load}
      pinnedBottomRowData={totals} emptyMessage="No orders yet."
    />
  );
}

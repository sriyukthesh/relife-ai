import { useCallback, useEffect, useMemo, useState } from "react";
import type { CellValueChangedEvent, ColDef } from "ag-grid-community";
import GridShell from "./GridShell";
import { ConditionCell, UsableCell } from "./cells";
import { fetchParts, removePart, updatePart, type PartRow } from "./dataSources";
import { CONDITIONS, conditionLabel, percent, specsText, titleCase, unusableReason, type Condition } from "./format";

const TESTED_WARNING =
  "Only mark this part as TESTED if you checked it with a meter or in a circuit. A photo cannot prove a part works.\n\nMark as tested?";

/** My parts as an editable data grid: inline edits are saved to the API and reverted if the server refuses. */
export default function InventoryGrid({ refreshKey = 0 }: { refreshKey?: number }) {
  const [rows, setRows] = useState<PartRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setRows(await fetchParts()); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load parts"); setRows([]); }
  }, []);
  useEffect(() => { load(); }, [load, refreshKey]);

  const columnDefs = useMemo<ColDef<PartRow>[]>(() => [
    { field: "label", headerName: "Part", editable: true, minWidth: 160, pinned: "left",
      filter: "agTextColumnFilter" },
    { field: "category", headerName: "Type", valueFormatter: (p) => titleCase(p.value), filter: "agTextColumnFilter" },
    { headerName: "Details", valueGetter: (p) => specsText(p.data?.specs), minWidth: 220, flex: 2, filter: "agTextColumnFilter" },
    { field: "quantity", headerName: "Qty", editable: true, filter: "agNumberColumnFilter", maxWidth: 110,
      cellEditor: "agNumberCellEditor", cellEditorParams: { min: 1, precision: 0, showStepperButtons: true },
      valueParser: (p) => Math.max(1, Math.round(Number(p.newValue)) || 1) },
    { field: "condition", headerName: "Condition", editable: true, minWidth: 170, cellRenderer: ConditionCell,
      cellEditor: "agSelectCellEditor", cellEditorParams: { values: [...CONDITIONS] },
      filter: "agTextColumnFilter", filterValueGetter: (p) => conditionLabel(p.data?.condition) },
    { headerName: "Used in builds?", valueGetter: (p) => (p.data ? unusableReason(p.data) : ""), cellRenderer: UsableCell, minWidth: 190 },
    { field: "source", headerName: "From", maxWidth: 120, filter: "agTextColumnFilter" },
    { field: "ai_confidence", headerName: "AI confidence", valueFormatter: (p) => percent(p.value),
      filter: "agNumberColumnFilter", maxWidth: 150 },
  ], []);

  const onCellValueChanged = useCallback(async (e: CellValueChangedEvent<PartRow>) => {
    const field = e.colDef.field as keyof PartRow | undefined;
    if (!e.data || !field || !["label", "quantity", "condition"].includes(field)) return;
    const revert = () => e.node.setData({ ...e.data!, [field]: e.oldValue }); // setData does not re-trigger this handler

    if (field === "condition" && e.newValue === "tested_ok" && !window.confirm(TESTED_WARNING)) { revert(); return; }
    if (field === "label" && !String(e.newValue ?? "").trim()) { revert(); return; }

    try {
      const saved = await updatePart(e.data.id, { [field]: e.newValue } as { quantity?: number; condition?: Condition; label?: string });
      e.node.setData(saved);
      setError(null);
    } catch (err) {
      revert();
      setError(err instanceof Error ? err.message : "Could not save that change");
    }
  }, []);

  const removeSelected = async (selected: PartRow[]) => {
    if (selected.length === 0 || !window.confirm(`Remove ${selected.length} selected part type(s)? This cannot be undone.`)) return;
    const failed: string[] = [];
    for (const r of selected) {
      try { await removePart(r.id); } catch { failed.push(r.label); }
    }
    await load();
    if (failed.length) setError(`Could not remove: ${failed.join(", ")}`);
  };

  return (
    <GridShell<PartRow>
      gridId="inventory" exportName="relife-my-parts" rowData={rows} columnDefs={columnDefs}
      getRowId={(p) => String(p.data.id)} error={error} selectable onRefresh={load}
      emptyMessage="No parts yet. Scan a photo or add one manually."
      onCellValueChanged={onCellValueChanged}
      getRowStyle={(p) => (p.data && !p.data.usable ? { background: "rgba(239,68,68,0.06)" } : undefined)}
      toolbar={(_api, selected) => (
        <button disabled={selected.length === 0} onClick={() => removeSelected(selected)}
          className="rounded-lg border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50">
          Remove selected{selected.length ? ` (${selected.length})` : ""}
        </button>
      )}
    />
  );
}

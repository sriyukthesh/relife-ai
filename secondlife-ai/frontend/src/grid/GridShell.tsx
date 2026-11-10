import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import { AgGridReact } from "ag-grid-react";
import type {
  CellValueChangedEvent, ColDef, GetRowIdParams, GridApi, GridReadyEvent, RowClassParams,
  RowSelectionOptions, RowStyle,
} from "ag-grid-community";
import { relifeTheme } from "./agSetup";
import { useGridPersist } from "./useGridPersist";

export interface GridShellProps<T> {
  gridId: string;
  rowData: T[] | null;
  columnDefs: ColDef<T>[];
  getRowId: (p: GetRowIdParams<T>) => string;
  exportName: string;
  emptyMessage: string;
  error?: string | null;
  height?: number;
  selectable?: boolean;
  paginate?: boolean;
  pageSize?: number;
  context?: unknown;
  pinnedBottomRowData?: Partial<T>[];
  onCellValueChanged?: (e: CellValueChangedEvent<T>) => void;
  getRowStyle?: (p: RowClassParams<T>) => RowStyle | undefined;
  onRefresh?: () => void;
  /** Extra toolbar content (e.g. bulk-action buttons). Receives the grid api and selected rows. */
  toolbar?: (api: GridApi<T> | null, selected: T[]) => ReactNode;
}

const btn = "rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-stone-100 disabled:opacity-50";

/** Shared look, search, CSV export, saved layout and states for every ReLife AI grid. */
export default function GridShell<T>(props: GridShellProps<T>) {
  const {
    gridId, rowData, columnDefs, getRowId, exportName, emptyMessage, error, height = 520,
    selectable = false, paginate = true, pageSize = 10, context, pinnedBottomRowData,
    onCellValueChanged, getRowStyle, onRefresh, toolbar,
  } = props;

  const apiRef = useRef<GridApi<T> | null>(null);
  const [quick, setQuick] = useState("");
  const [selected, setSelected] = useState<T[]>([]);
  const [shown, setShown] = useState<number | null>(null);
  const persist = useGridPersist(gridId);

  const defaultColDef = useMemo<ColDef<T>>(
    () => ({ sortable: true, filter: true, resizable: true, floatingFilter: true, minWidth: 90, flex: 1 }),
    [],
  );
  const rowSelection = useMemo<RowSelectionOptions | undefined>(
    () => (selectable ? { mode: "multiRow", checkboxes: true, headerCheckbox: true, enableClickSelection: false } : undefined),
    [selectable],
  );

  const refreshCounts = useCallback(() => {
    const api = apiRef.current;
    if (api) setShown(api.getDisplayedRowCount());
  }, []);

  const onGridReady = useCallback((e: GridReadyEvent<T>) => {
    apiRef.current = e.api;
    persist.restore(e.api as GridApi);
  }, [persist]);

  const saveLayout = useCallback(() => {
    if (apiRef.current) persist.save(apiRef.current as GridApi);
  }, [persist]);

  const api = apiRef.current;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <input
          className="min-w-[12rem] flex-1 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm"
          placeholder="Search this table…" value={quick} aria-label="Search table"
          onChange={(e) => setQuick(e.target.value)}
        />
        {toolbar?.(api, selected)}
        {onRefresh && <button className={btn} onClick={onRefresh}>Refresh</button>}
        <button className={btn} onClick={() => apiRef.current?.exportDataAsCsv({ fileName: `${exportName}.csv` })}>Export CSV</button>
        {selectable && (
          <button className={btn} disabled={selected.length === 0}
            onClick={() => apiRef.current?.exportDataAsCsv({ fileName: `${exportName}-selected.csv`, onlySelected: true })}>
            Export selected
          </button>
        )}
        <button className={btn} onClick={() => apiRef.current && persist.reset(apiRef.current as GridApi)}>Reset layout</button>
      </div>

      {error && <div role="alert" className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>}

      <div style={{ height }}>
        <AgGridReact<T>
          theme={relifeTheme}
          rowData={rowData ?? []}
          loading={rowData === null}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          getRowId={getRowId}
          rowSelection={rowSelection}
          quickFilterText={quick}
          pagination={paginate}
          paginationPageSize={pageSize}
          paginationPageSizeSelector={[10, 25, 50]}
          pinnedBottomRowData={pinnedBottomRowData}
          context={context}
          getRowStyle={getRowStyle}
          overlayNoRowsTemplate={`<span style="padding:12px">${emptyMessage}</span>`}
          suppressCellFocus={!onCellValueChanged}
          stopEditingWhenCellsLoseFocus
          onGridReady={onGridReady}
          onCellValueChanged={onCellValueChanged}
          onSelectionChanged={(e) => setSelected(e.api.getSelectedRows())}
          onFirstDataRendered={refreshCounts}
          onFilterChanged={refreshCounts}
          onRowDataUpdated={refreshCounts}
          onSortChanged={saveLayout}
          onColumnMoved={saveLayout}
          onColumnVisible={saveLayout}
          onColumnResized={(e) => e.finished && saveLayout()}
        />
      </div>
      <p className="text-xs text-stone-500">
        {rowData ? `${shown ?? rowData.length} of ${rowData.length} rows` : "Loading…"} · Click a header to sort, use the boxes under it to filter.
      </p>
    </div>
  );
}

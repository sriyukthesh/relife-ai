import { useCallback, useEffect, useRef } from "react";
import type { ColumnState, GridApi } from "ag-grid-community";

const key = (id: string) => `relife.grid.${id}.v1`;

/** Remember column order, width, sort and visibility per grid in this browser. */
export function useGridPersist(gridId: string) {
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const restore = useCallback((api: GridApi) => {
    try {
      const raw = localStorage.getItem(key(gridId));
      if (raw) api.applyColumnState({ state: JSON.parse(raw) as ColumnState[], applyOrder: true });
    } catch { /* storage unavailable or corrupt: use defaults */ }
  }, [gridId]);

  const save = useCallback((api: GridApi) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      if (api.isDestroyed()) return;
      try { localStorage.setItem(key(gridId), JSON.stringify(api.getColumnState())); } catch { /* ignore */ }
    }, 300);
  }, [gridId]);

  const reset = useCallback((api: GridApi) => {
    try { localStorage.removeItem(key(gridId)); } catch { /* ignore */ }
    api.resetColumnState();
    api.setFilterModel(null);
  }, [gridId]);

  return { restore, save, reset };
}

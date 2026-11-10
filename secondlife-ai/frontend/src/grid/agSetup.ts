/**
 * One-time AG Grid setup (Community edition, MIT licence: no enterprise features are used).
 * Import this file before rendering any grid; GridShell does it for you.
 *
 * Targets AG Grid 33.x: modules are registered explicitly and styling uses the
 * Theming API (no CSS file imports needed).
 */
import {
  ClientSideRowModelModule,
  ColumnApiModule,
  CsvExportModule,
  DateFilterModule,
  ModuleRegistry,
  NumberEditorModule,
  NumberFilterModule,
  PaginationModule,
  PinnedRowModule,
  QuickFilterModule,
  RowApiModule,
  RowSelectionModule,
  RowStyleModule,
  SelectEditorModule,
  TextEditorModule,
  TextFilterModule,
  themeQuartz,
} from "ag-grid-community";

let registered = false;
export function ensureGridModules(): void {
  if (registered) return;
  ModuleRegistry.registerModules([
    ClientSideRowModelModule,
    ColumnApiModule,
    CsvExportModule,
    DateFilterModule,
    NumberEditorModule,
    NumberFilterModule,
    PaginationModule,
    PinnedRowModule,
    QuickFilterModule,
    RowApiModule,
    RowSelectionModule,
    RowStyleModule,
    SelectEditorModule,
    TextEditorModule,
    TextFilterModule,
  ]);
  registered = true;
}
ensureGridModules();

/** ReLife AI look: emerald accent, rounded, compact. */
export const relifeTheme = themeQuartz.withParams({
  accentColor: "#047857",
  fontFamily: "inherit",
  fontSize: 14,
  headerFontWeight: 600,
  borderRadius: 8,
  wrapperBorderRadius: 12,
  spacing: 7,
  selectedRowBackgroundColor: "rgba(4, 120, 87, 0.08)",
});

// Wires AG Grid into the app automatically. Run from the frontend/ folder:
//   node scripts/wire-aggrid.mjs
// It (1) adds ag-grid deps to package.json, (2) adds a "Data tables" tab to src/App.tsx.
// Backups: package.json.bak and src/App.tsx.bak. If App.tsx does not look as expected,
// nothing in App.tsx is changed and exact manual steps are printed instead.
import { copyFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";

const PKG = "package.json";
const APP = "src/App.tsx";
const AG_VERSION = "^33.0.0";

if (!existsSync(PKG) || !existsSync(APP)) {
  console.error("Run this from the frontend/ folder (package.json and src/App.tsx must exist).");
  process.exit(1);
}

// ---- 1. package.json ----
const pkg = JSON.parse(readFileSync(PKG, "utf8"));
pkg.dependencies ??= {};
let pkgChanged = false;
for (const d of ["ag-grid-community", "ag-grid-react"]) {
  if (!pkg.dependencies[d]) { pkg.dependencies[d] = AG_VERSION; pkgChanged = true; }
}
if (pkgChanged) {
  copyFileSync(PKG, PKG + ".bak");
  writeFileSync(PKG, JSON.stringify(pkg, null, 2) + "\n");
  console.log(`package.json: added ag-grid-community and ag-grid-react ${AG_VERSION}`);
} else console.log("package.json: ag-grid already listed");

// ---- 2. App.tsx ----
let src = readFileSync(APP, "utf8");
const manual = (why) => {
  console.log(`\nApp.tsx NOT changed (${why}). Do these 3 things by hand:`);
  console.log(`  1. import DataGrids from "./pages/DataGrids";`);
  console.log(`  2. add a tab entry ["grids", "Data tables"] to your tab list and "grids" to the Tab type`);
  console.log(`  3. render:  {tab === "grids" && <DataGrids />}   (pass onAddToCart={yourCartFunction} to enable the cart button)`);
};

if (src.includes("DataGrids")) {
  console.log("App.tsx: already wired");
} else {
  const typeRe = /type Tab\s*=\s*([^;]+);/;
  const tabsRe = /(const TABS[^=]*=\s*\[)([\s\S]*?)(\n?\s*\];)/;
  const renderRe = /^([ \t]*)\{tab === "[A-Za-z-]+" && .*\}[ \t]*$/gm;
  const imports = [...src.matchAll(/^import .*;$/gm)];
  const renders = [...src.matchAll(renderRe)];

  if (!typeRe.test(src) || !tabsRe.test(src) || renders.length === 0 || imports.length === 0) {
    manual("the Tab type, TABS list or tab render lines were not found in the expected form");
  } else {
    const backup = src;
    // render line (insert after the last existing one)
    const last = renders[renders.length - 1];
    const at = last.index + last[0].length;
    src = src.slice(0, at) + `\n${last[1]}{tab === "grids" && <DataGrids />}` + src.slice(at);
    // TABS list
    src = src.replace(tabsRe, (_m, a, body, c) => {
      const b = body.trimEnd();
      return `${a}${b}${b.endsWith(",") ? "" : ","} ["grids", "Data tables"],${c}`;
    });
    // Tab type
    src = src.replace(typeRe, (_m, t) => `type Tab = ${t.trim()} | "grids";`);
    // import (after the last import)
    const li = imports[imports.length - 1];
    const ip = src.indexOf(li[0]) + li[0].length;
    src = src.slice(0, ip) + `\nimport DataGrids from "./pages/DataGrids";` + src.slice(ip);

    copyFileSync(APP, APP + ".bak");
    writeFileSync(APP, src);
    console.log('App.tsx: added the "Data tables" tab (backup: src/App.tsx.bak)');
    void backup;
  }
}

console.log("\nNext: run  npm install  then  npm run dev");

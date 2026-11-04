import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "../api";
import ConfirmCard, { draftFromProposal } from "../components/ConfirmCard";
import { errText, ErrorBanner, Notice } from "../components/ui";
import type {
  Build, BuildPhotoCheck, Catalog, ComponentTestResult, InventoryItem, LedResistorResult, Proposal,
  ResistorOption, TeardownAssessment, TestProcedure,
} from "../types";

const TESTABLE = new Set(["resistor", "potentiometer", "diode", "led", "capacitor", "battery", "button"]);
const BOOLEAN_INPUTS = new Set([
  "wiper_sweeps_smoothly", "reverse_open", "lights_up", "continuity_when_pressed", "open_when_released",
]);
const LABELS: Record<string, string> = {
  measured_ohm: "Measured resistance (Ω)",
  wiper_sweeps_smoothly: "Does the wiper sweep smoothly?",
  forward_v: "Forward voltage (V)",
  reverse_open: "Does reverse direction show open (OL)?",
  lights_up: "Does the LED light in correct polarity?",
  measured_uf: "Measured capacitance (µF)",
  measured_v: "Measured voltage (V)",
  continuity_when_pressed: "Continuity when pressed?",
  open_when_released: "Open when released?",
};

function isBooleanInput(key: string) {
  return BOOLEAN_INPUTS.has(key);
}

export default function Workbench({ catalog, onChanged }: { catalog: Catalog; onChanged: () => void }) {
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [build, setBuild] = useState<Build | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const items = await api.inventory();
      setInventory(items);
      setError(null);
    } catch (e) {
      setError(errText(e));
    }
    try {
      setBuild(await api.currentBuild());
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setBuild(null);
      else setError(errText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const [deviceName, setDeviceName] = useState("");
  const [salvageFile, setSalvageFile] = useState<File | null>(null);
  const [salvage, setSalvage] = useState<TeardownAssessment | null>(null);
  const [closedProposals, setClosedProposals] = useState<Set<number>>(new Set());
  const [salvageBusy, setSalvageBusy] = useState(false);

  const assessSalvage = async (event: FormEvent) => {
    event.preventDefault();
    if (!salvageFile) return;
    setSalvageBusy(true);
    setError(null);
    try {
      setSalvage(await api.teardown(salvageFile, deviceName));
      setClosedProposals(new Set());
    } catch (e) {
      setError(errText(e));
    } finally {
      setSalvageBusy(false);
    }
  };

  const [targetOhm, setTargetOhm] = useState("440");
  const [tolerance, setTolerance] = useState("10");
  const [resistorOptions, setResistorOptions] = useState<ResistorOption[] | null>(null);
  const [ledSupply, setLedSupply] = useState("5");
  const [ledForward, setLedForward] = useState("2");
  const [ledCurrent, setLedCurrent] = useState("10");
  const [ledResult, setLedResult] = useState<LedResistorResult | null>(null);

  const findSubstitutes = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setResistorOptions(null);
    try {
      const result = await api.resistorSubstitutes(Number(targetOhm), Number(tolerance) / 100);
      setResistorOptions(result.options);
    } catch (e) {
      setError(errText(e));
    }
  };

  const calculateLed = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLedResult(null);
    try {
      setLedResult(await api.ledResistor(Number(ledSupply), Number(ledForward), Number(ledCurrent)));
    } catch (e) {
      setError(errText(e));
    }
  };

  const testableItems = useMemo(() => inventory.filter((item) => TESTABLE.has(item.category)), [inventory]);
  const [selectedItemId, setSelectedItemId] = useState("");
  const selectedItem = testableItems.find((item) => item.id === Number(selectedItemId)) ?? null;
  const [procedure, setProcedure] = useState<TestProcedure | null>(null);
  const [measurements, setMeasurements] = useState<Record<string, string | boolean | null>>({});
  const [confirmed, setConfirmed] = useState(false);
  const [testResult, setTestResult] = useState<ComponentTestResult | null>(null);
  const [testBusy, setTestBusy] = useState(false);

  useEffect(() => {
    setProcedure(null);
    setMeasurements({});
    setConfirmed(false);
    setTestResult(null);
    if (!selectedItem) return;
    api.testProcedure(selectedItem.category)
      .then((result) => {
        setProcedure(result);
        setMeasurements(Object.fromEntries(result.inputs.map((input) => [
          input, isBooleanInput(input) ? null : "",
        ])));
      })
      .catch((e) => setError(errText(e)));
  }, [selectedItem?.id, selectedItem?.category]);

  const submitTest = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedItem || !procedure || !confirmed) return;
    const values: Record<string, number | boolean> = {};
    for (const input of procedure.inputs) {
      const value = measurements[input];
      if (isBooleanInput(input)) {
        if (typeof value !== "boolean") {
          setError(`Choose Yes or No for ${LABELS[input] ?? input}.`);
          return;
        }
        values[input] = value;
      }
      else {
        const numeric = Number(value);
        if (value === "" || !Number.isFinite(numeric)) {
          setError(`Enter a valid value for ${LABELS[input] ?? input}.`);
          return;
        }
        values[input] = numeric;
      }
    }
    setTestBusy(true);
    setError(null);
    try {
      setTestResult(await api.completeTest(selectedItem.id, values));
      await load();
      onChanged();
    } catch (e) {
      setError(errText(e));
    } finally {
      setTestBusy(false);
    }
  };

  const [photo, setPhoto] = useState<File | null>(null);
  const [photoNote, setPhotoNote] = useState("");
  const [photoResult, setPhotoResult] = useState<BuildPhotoCheck | null>(null);
  const [photoBusy, setPhotoBusy] = useState(false);
  const checkPhoto = async (event: FormEvent) => {
    event.preventDefault();
    if (!build || !photo) return;
    setPhotoBusy(true);
    setError(null);
    try {
      setPhotoResult(await api.checkBuildPhoto(build.id, photo, photoNote));
    } catch (e) {
      setError(errText(e));
    } finally {
      setPhotoBusy(false);
    }
  };

  if (loading) return <p className="text-sm text-stone-500">Loading tools…</p>;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">Tools and testing</h1>
        <p className="mt-1 text-sm text-stone-600">Use deterministic calculators and guided checks; AI results are suggestions, never safety certifications.</p>
      </div>
      <ErrorBanner message={error} />

      <section className="card space-y-3">
        <div>
          <h2 className="font-display text-xl font-bold">Assess a device for salvage</h2>
          <p className="text-sm text-stone-600">Get visual proposals only. No component is saved or certified by this check.</p>
        </div>
        <form onSubmit={assessSalvage} className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">Device name or description
            <input className="input mt-1" value={deviceName} maxLength={160} onChange={(e) => setDeviceName(e.target.value)} placeholder="e.g. low-voltage toy" />
          </label>
          <label className="text-sm">Device photo (JPEG, PNG, WebP)
            <input className="input mt-1" type="file" accept="image/jpeg,image/png,image/webp" required onChange={(e) => setSalvageFile(e.target.files?.[0] ?? null)} />
          </label>
          <button className="btn-primary sm:col-span-2" disabled={!salvageFile || salvageBusy}>
            {salvageBusy ? "Assessing…" : "Assess for salvage"}
          </button>
        </form>
        {salvage && (
          <div className="space-y-3" aria-live="polite">
            {salvage.blocked ? (
              <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900">
                <strong>Do not open or harvest this device.</strong>
                <ul className="mt-1 list-disc pl-5">{salvage.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
              </div>
            ) : (
              <>
                <Notice>{salvage.device_guess || "Device could not be identified"} — this is an AI visual proposal, not an electrical test.</Notice>
                {salvage.components.length === 0 && <p className="text-sm text-stone-600">No components were proposed.</p>}
                {salvage.components.map((component, index) => (
                  <div className="space-y-2" key={`${component.label}-${index}`}>
                    <div className="rounded-lg border border-stone-200 p-3 text-sm">
                      <p className="font-medium">{component.label} <span className="text-stone-500">· {component.category}</span></p>
                      <p className="text-stone-600">Marking: {component.marking || "not readable"} · {component.location_hint || "location unclear"} · {Math.round(component.confidence * 100)}% confidence</p>
                      {component.damage_flags.length > 0 && <p className="mt-1 text-red-700">Damage flags: {component.damage_flags.join(", ")}</p>}
                      <p className={component.worth_harvesting ? "mt-1 text-emerald-800" : "mt-1 text-amber-800"}>
                        {component.worth_harvesting ? "Potentially worth inspecting" : "Do not harvest based on this assessment"}
                      </p>
                      {component.extraction_tip && <p className="mt-1">{component.extraction_tip}</p>}
                    </div>
                    {component.worth_harvesting && !closedProposals.has(index) && (() => {
                      const proposal: Proposal = {
                        proposal_id: `salvage-${index}`,
                        category: component.category,
                        label: component.label,
                        specs: {},
                        quantity: 1,
                        suggested_condition: component.suggested_condition,
                        ai_confidence: component.confidence,
                        needs_review: component.confidence < 0.7,
                        missing_required_specs: [],
                        visible_markings: component.marking ?? "",
                        damage_flags: component.damage_flags,
                        uncertainties: component.location_hint ? [] : ["Location is uncertain."],
                        evidence: [component.location_hint, component.extraction_tip].filter(Boolean).join(" "),
                        box: null,
                        box_source: "none",
                      };
                      return (
                        <ConfirmCard
                          draft={draftFromProposal(proposal)}
                          catalog={catalog}
                          source="scan"
                          index={index}
                          onSkip={() => setClosedProposals((current) => new Set(current).add(index))}
                          onConfirm={async (item) => {
                            await api.addItem(item);
                            setClosedProposals((current) => new Set(current).add(index));
                            await load();
                            onChanged();
                          }}
                        />
                      );
                    })()}
                  </div>
                ))}
              </>
            )}
            {salvage.warnings.map((warning, index) => <p className="text-sm text-amber-800" key={index}>{warning}</p>)}
            <ul className="list-disc space-y-1 pl-5 text-xs text-stone-600">{salvage.safety_steps.map((step) => <li key={step}>{step}</li>)}</ul>
          </div>
        )}
      </section>

      <section className="card space-y-3">
        <div>
          <h2 className="font-display text-xl font-bold">Resistor substitutions</h2>
          <p className="text-sm text-stone-600">Find single, series, or parallel combinations using your non-damaged inventory.</p>
        </div>
        <form onSubmit={findSubstitutes} className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">Target resistance (Ω)
            <input className="input mt-1" type="number" min="0.000001" step="any" required value={targetOhm} onChange={(e) => setTargetOhm(e.target.value)} />
          </label>
          <label className="text-sm">Allowed error (%)
            <input className="input mt-1" type="number" min="0" max="100" step="any" required value={tolerance} onChange={(e) => setTolerance(e.target.value)} />
          </label>
          <button className="btn-primary self-end">Find combinations</button>
        </form>
        {resistorOptions && (
          <div className="space-y-2" aria-live="polite">
            {resistorOptions.length === 0 && <p className="text-sm text-stone-600">No matching combination in your current parts.</p>}
            {resistorOptions.map((option, index) => (
              <div className="rounded-lg bg-stone-50 p-3 text-sm" key={`${option.kind}-${index}`}>
                <p className="font-medium">{option.result_ohm} Ω · {option.kind} · {option.error_pct}% error</p>
                <p className="text-stone-600">{option.how}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card space-y-3">
        <div>
          <h2 className="font-display text-xl font-bold">LED resistor calculator</h2>
          <p className="text-sm text-stone-600">The standard value is rounded upward so the calculated current does not exceed your target.</p>
        </div>
        <form onSubmit={calculateLed} className="grid gap-3 sm:grid-cols-4">
          <label className="text-sm">Supply (V)<input className="input mt-1" type="number" min="0" step="any" required value={ledSupply} onChange={(e) => setLedSupply(e.target.value)} /></label>
          <label className="text-sm">LED forward (V)<input className="input mt-1" type="number" min="0" step="any" required value={ledForward} onChange={(e) => setLedForward(e.target.value)} /></label>
          <label className="text-sm">Target current (mA)<input className="input mt-1" type="number" min="1" max="30" step="any" required value={ledCurrent} onChange={(e) => setLedCurrent(e.target.value)} /></label>
          <button className="btn-primary self-end">Calculate</button>
        </form>
        {ledResult && <Notice>Use {ledResult.chosen_ohm} Ω ({ledResult.actual_current_ma} mA calculated, {ledResult.resistor_power_mw} mW). {ledResult.note}.</Notice>}
      </section>

      <section className="card space-y-3">
        <div>
          <h2 className="font-display text-xl font-bold">Guided component test</h2>
          <p className="text-sm text-stone-600">You provide meter readings and confirm them; deterministic checks update one unit in inventory.</p>
        </div>
        <label className="block text-sm">Part to test
          <select className="input mt-1" value={selectedItemId} onChange={(e) => setSelectedItemId(e.target.value)}>
            <option value="">Choose a supported part</option>
            {testableItems.map((item) => <option value={item.id} key={item.id}>{item.label} · {item.category} · qty {item.quantity}</option>)}
          </select>
        </label>
        {testableItems.length === 0 && <p className="text-sm text-stone-600">No supported components are in inventory yet.</p>}
        {selectedItem && procedure && (
          <form onSubmit={submitTest} className="space-y-3">
            <p className="text-sm font-medium">Tool: {procedure.tool}</p>
            <ol className="list-decimal space-y-1 pl-5 text-sm text-stone-700">{procedure.steps.map((step) => <li key={step}>{step}</li>)}</ol>
            <div className="grid gap-3 sm:grid-cols-2">
              {procedure.inputs.map((input) => (
                <label className="text-sm" key={input}>{LABELS[input] ?? input}
                  {isBooleanInput(input) ? (
                    <select className="input mt-1" required
                      value={measurements[input] === null ? "" : String(measurements[input])}
                      onChange={(e) => setMeasurements((current) => ({ ...current, [input]: e.target.value === "true" }))}>
                      <option value="" disabled>Choose an answer</option>
                      <option value="false">No</option>
                      <option value="true">Yes</option>
                    </select>
                  ) : (
                    <input className="input mt-1" type="number" step="any" required
                      value={String(measurements[input] ?? "")}
                      onChange={(e) => setMeasurements((current) => ({ ...current, [input]: e.target.value }))} />
                  )}
                </label>
              ))}
            </div>
            <label className="flex items-start gap-2 text-sm text-stone-700">
              <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
              I personally took these measurements and confirm they are accurate.
            </label>
            <button className="btn-primary" disabled={!confirmed || testBusy}>{testBusy ? "Checking…" : "Submit test result"}</button>
          </form>
        )}
        {testResult && (
          <Notice>
            {testResult.verdict === "pass" ? "Test passed." : testResult.verdict === "fail" ? "Test did not pass." : "This test is not supported."}
            {" "}{testResult.reason}
            {testResult.new_condition && ` Inventory condition updated to ${testResult.new_condition.replace("_", " ")}.`}
          </Notice>
        )}
      </section>

      <section className="card space-y-3">
        <div>
          <h2 className="font-display text-xl font-bold">Check a build photo</h2>
          <p className="text-sm text-stone-600">Photo review can point out likely mistakes but cannot certify a circuit as safe or working.</p>
        </div>
        {!build ? <p className="text-sm text-stone-600">Start a guided build to check its current step.</p> : (
          <>
            <p className="text-sm font-medium">{build.title} · step {build.step.index + 1} of {build.total_steps}: {build.step.title}</p>
            <form onSubmit={checkPhoto} className="space-y-3">
              <label className="block text-sm">Build photo (JPEG, PNG, WebP)
                <input className="input mt-1" type="file" accept="image/jpeg,image/png,image/webp" required onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
              </label>
              <label className="block text-sm">What should the AI look at?
                <input className="input mt-1" value={photoNote} maxLength={300} onChange={(e) => setPhotoNote(e.target.value)} placeholder="e.g. LED direction and resistor placement" />
              </label>
              <button className="btn-primary" disabled={!photo || photoBusy}>{photoBusy ? "Checking…" : "Check photo"}</button>
            </form>
            {photoResult?.safety_stop && <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-900">{photoResult.message}</div>}
            {photoResult && !photoResult.safety_stop && (
              photoResult.available === false ? <Notice>{photoResult.message}</Notice> : (
                <div className="space-y-2 text-sm" aria-live="polite">
                  <Notice>{photoResult.looks_consistent ? "No obvious mismatch found." : "Possible mismatch found."} Confidence: {Math.round((photoResult.confidence ?? 0) * 100)}%. {photoResult.disclaimer}</Notice>
                  {photoResult.issues?.map((issue, index) => <p className="text-red-800" key={`issue-${index}`}>Possible issue: {issue}</p>)}
                  {photoResult.things_to_verify?.map((item, index) => <p className="text-stone-700" key={`verify-${index}`}>Verify: {item}</p>)}
                </div>
              )
            )}
          </>
        )}
      </section>
    </div>
  );
}

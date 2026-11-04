import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { IconSpark, IconSpeaker } from "../components/Icons";
import { errText, ErrorBanner, Notice } from "../components/ui";
import type { Build as BuildT } from "../types";

function speak(text: string) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.95;
  window.speechSynthesis.speak(u);
}

export default function Build({ onGoRecommend, onOpenCopilot }: { onGoRecommend: () => void; onOpenCopilot: () => void }) {
  const [build, setBuild] = useState<BuildT | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRead, setAutoRead] = useState(true);
  const lastSpoken = useRef<string>("");

  const load = useCallback(async () => {
    try { setBuild(await api.currentBuild()); }
    catch (e) { if (!(e instanceof ApiError && e.status === 404)) setError(errText(e)); setBuild(null); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); return () => window.speechSynthesis?.cancel(); }, [load]);

  const stepText = build ? `Step ${build.step.index + 1} of ${build.total_steps}. ${build.step.title}. ${build.step.instruction}` : "";
  useEffect(() => {
    if (build && autoRead && lastSpoken.current !== `${build.id}:${build.step.index}`) {
      lastSpoken.current = `${build.id}:${build.step.index}`;
      speak(stepText);
    }
  }, [build, autoRead, stepText]);

  const move = async (fn: (id: number) => Promise<BuildT>) => {
    if (!build) return;
    try { setBuild(await fn(build.id)); setError(null); } catch (e) { setError(errText(e)); }
  };

  if (loading) return <p className="text-sm text-stone-500">Loading…</p>;
  if (!build) {
    return (
      <div className="space-y-4">
        <h1 className="page-title">Guided build</h1>
        <div className="card space-y-2">
          <ErrorBanner message={error} />
          <p className="text-sm text-stone-700">No build in progress. Pick a project and I’ll walk you through it step by step.</p>
          <div className="flex flex-wrap gap-2">
            <button className="btn-primary" onClick={onGoRecommend}>Pick a project</button>
            <button className="btn-ghost" onClick={onOpenCopilot}><IconSpark size={16} /> Ask Copilot instead</button>
          </div>
        </div>
      </div>
    );
  }

  const done = build.status === "completed";
  return (
    <div className="space-y-4">
      <h1 className="page-title">Guided build</h1>
      <ErrorBanner message={error} />
      <div className="card space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-display text-xl font-bold">{build.title}</h2>
          <label className="flex items-center gap-1 text-xs text-stone-600">
            <input type="checkbox" checked={autoRead} onChange={(e) => setAutoRead(e.target.checked)} /> Read steps aloud
          </label>
        </div>
        <div className="h-1.5 overflow-hidden rounded bg-stone-100">
          <div className="h-full bg-emerald-600" style={{ width: `${((build.step.index + (done ? 1 : 0)) / build.total_steps) * 100}%` }} />
        </div>
        {done ? (
          <Notice>Build finished. Nice work! Test the circuit carefully, and mark parts you verified as “Tested” in My parts. It now counts on your dashboard.</Notice>
        ) : (
          <div>
            <p className="text-xs text-stone-500">Step {build.step.index + 1} of {build.total_steps}</p>
            <h3 className="font-display text-xl font-bold">{build.step.title}</h3>
            <p className="mt-1 text-stone-700">{build.step.instruction}</p>
          </div>
        )}
        {build.safety_note && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-800">⚠ {build.safety_note}</p>}
        {build.warnings.length > 0 && <p className="text-xs text-amber-800">{build.warnings.join(" ")}</p>}
        {build.missing_parts.length > 0 && (
          <p className="text-xs text-red-700">Still missing: {build.missing_parts.map((m) => `${m.quantity} x ${m.label}`).join(", ")}</p>
        )}
        {!done && (
          <div className="flex flex-wrap gap-2">
            <button className="btn-ghost" disabled={build.step.index === 0} onClick={() => move(api.prevStep)}>← Previous</button>
            <button className="btn-ghost" onClick={() => speak(stepText)}><IconSpeaker size={16} /> Read again</button>
            {build.is_last
              ? <button className="btn-primary" onClick={() => move(api.finishBuild)}>Finish</button>
              : <button className="btn-primary" onClick={() => move(api.nextStep)}>Next →</button>}
          </div>
        )}
      </div>

      {!done && (
        <div className="card flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold">Stuck on this step?</h3>
            <p className="text-sm text-stone-600">Ask Copilot by voice or text, or send a photo of your wiring. It already knows this project and step.</p>
          </div>
          <button className="btn-primary" onClick={onOpenCopilot}><IconSpark size={16} /> Open Copilot</button>
        </div>
      )}
      {done && <button className="btn-primary" onClick={onGoRecommend}>Back to projects</button>}
    </div>
  );
}

import { useEffect, useState } from "react";
import { api } from "../api";
import CameraCapture from "../components/CameraCapture";
import ConfirmCard, { blankDraft, draftFromProposal } from "../components/ConfirmCard";
import { IconCamera, IconImage, IconTag } from "../components/Icons";
import ListingAssistant from "../components/ListingAssistant";
import { shrinkImage } from "../components/imageUtil";
import { errText, ErrorBanner, Notice } from "../components/ui";
import type { Catalog, InspectResponse } from "../types";

const cameraOk = () => Boolean(navigator.mediaDevices?.getUserMedia) && window.isSecureContext;

interface Added { id: number; label: string; qty: number }

export default function Scan({ catalog, onAdded }: { catalog: Catalog; onAdded: () => void }) {
  const [mode, setMode] = useState<"camera" | "upload">(cameraOk() ? "camera" : "upload");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<InspectResponse | null>(null);
  const [done, setDone] = useState<Set<string>>(new Set());
  const [manual, setManual] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState<Added[]>([]);
  const [sellIdx, setSellIdx] = useState<number | null>(null);

  useEffect(() => {
    if (!file) { setPreview(null); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const analyse = async (f: File) => {
    setBusy(true); setError(null); setResult(null); setDone(new Set());
    try { setResult(await api.inspect(f)); } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  };

  /** A new photo (camera or upload) is analysed straight away. */
  const take = async (raw: File | null) => {
    if (!raw) return;
    const f = await shrinkImage(raw);
    setFile(f);
    analyse(f);
  };
  const retake = () => { setFile(null); setResult(null); setDone(new Set()); setError(null); };

  const close = (id: string) => setDone((d) => new Set(d).add(id));
  const open = result?.proposals.filter((p) => !done.has(p.proposal_id)) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Scan parts</h1>
        <p className="mt-1 text-sm text-stone-600">Take a photo and the system proposes what each part is. You confirm or correct every one before it is saved.</p>
      </div>

      <section className="space-y-3">
        {!file && (
          <div className="inline-flex rounded-lg border border-stone-300 bg-white p-0.5 text-sm" role="tablist" aria-label="Photo source">
            <button role="tab" aria-selected={mode === "camera"} onClick={() => setMode("camera")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 ${mode === "camera" ? "bg-emerald-600 text-white" : "text-stone-700"}`}><IconCamera size={16} /> Live camera</button>
            <button role="tab" aria-selected={mode === "upload"} onClick={() => setMode("upload")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 ${mode === "upload" ? "bg-emerald-600 text-white" : "text-stone-700"}`}><IconImage size={16} /> Upload photo</button>
          </div>
        )}

        {!file && mode === "camera" && (
          <div className="max-w-xl"><CameraCapture onCapture={take} onClose={() => setMode("upload")} hint="Spread parts on a plain surface. Fewer parts per photo gives better results." /></div>
        )}
        {!file && mode === "upload" && (
          <label className="flex max-w-xl cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-stone-300 bg-white px-6 py-10 text-center text-sm text-stone-600 hover:border-emerald-500">
            <IconImage size={28} className="text-emerald-600" />
            <span className="font-medium text-stone-800">Choose a photo of your parts</span>
            <span>JPEG, PNG or WebP. On a phone this can open the camera.</span>
            <input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(e) => { take(e.target.files?.[0] ?? null); e.target.value = ""; }} />
          </label>
        )}

        {file && preview && (
          <div className="space-y-3">
            <div className="relative inline-block max-w-full">
              <img src={preview} alt="Your parts" className="max-h-[26rem] rounded-xl" />
              {result?.proposals.map((p, i) => p.box && (
                <div key={p.proposal_id} className={`absolute border-2 ${done.has(p.proposal_id) ? "border-stone-400" : "border-gold"}`}
                  style={{
                    left: `${(p.box[0] / result.image_width) * 100}%`, top: `${(p.box[1] / result.image_height) * 100}%`,
                    width: `${((p.box[2] - p.box[0]) / result.image_width) * 100}%`, height: `${((p.box[3] - p.box[1]) / result.image_height) * 100}%`,
                  }}>
                  <span className="absolute left-0 top-0 bg-gold px-1 text-xs font-medium text-white">{i + 1}</span>
                </div>
              ))}
              {busy && (
                <div className="absolute inset-0 grid place-items-center rounded-xl bg-ink/60 text-sm font-medium text-white" role="status">Identifying parts…</div>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="btn-ghost" onClick={retake} disabled={busy}><IconCamera size={16} /> Take another photo</button>
              <button className="btn-ghost" onClick={() => file && analyse(file)} disabled={busy}>Analyse again</button>
            </div>
          </div>
        )}
      </section>

      <ErrorBanner message={error} />

      {result && (
        <section className="space-y-3">
          <h2 className="font-display text-xl font-bold">Confirm or correct each part</h2>
          <Notice>{result.disclaimer}</Notice>
          {result.notes.map((n, i) => <p key={i} className="text-xs text-stone-500">{n}</p>)}
          {open.length === 0 && <p className="text-sm text-stone-600">Nothing left to review. Add a missed part manually below if needed.</p>}
          {result.proposals.map((p, i) => !done.has(p.proposal_id) && (
            <ConfirmCard key={p.proposal_id} draft={draftFromProposal(p)} catalog={catalog} source="scan" index={i}
              onSkip={() => close(p.proposal_id)}
              onConfirm={async (item) => {
                const saved = await api.addItem(item);
                close(p.proposal_id);
                setAdded((a) => [...a, { id: saved.id, label: saved.label, qty: item.quantity }]);
                onAdded();
              }} />
          ))}
        </section>
      )}

      {added.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-display text-xl font-bold">Added to My parts</h2>
          <p className="text-sm text-stone-600">Got spares? List them for other makers in one step.</p>
          <ul className="space-y-2">
            {added.map((a, i) => (
              <li key={i} className="card space-y-3">
                <div className="flex flex-wrap items-center gap-3">
                  <p className="min-w-0 flex-1 text-sm"><span className="font-medium">{a.qty} × {a.label}</span> saved</p>
                  <button className="btn-ghost" onClick={() => setSellIdx(sellIdx === i ? null : i)}><IconTag size={16} /> {sellIdx === i ? "Hide" : "Sell on marketplace"}</button>
                </div>
                {sellIdx === i && <ListingAssistant itemId={a.id} onListed={() => onAdded()} onClose={() => setSellIdx(null)} />}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="space-y-3">
        <button className="btn-ghost" onClick={() => setManual((m) => m + 1)}>+ Add a part manually</button>
        {Array.from({ length: manual }).map((_, i) => (
          <ConfirmCard key={`m${i}`} draft={blankDraft()} catalog={catalog} source="manual"
            onSkip={() => setManual((m) => Math.max(0, m - 1))}
            onConfirm={async (item) => {
              const saved = await api.addItem(item);
              setManual((m) => Math.max(0, m - 1));
              setAdded((a) => [...a, { id: saved.id, label: saved.label, qty: item.quantity }]);
              onAdded();
            }} />
        ))}
      </div>
    </div>
  );
}

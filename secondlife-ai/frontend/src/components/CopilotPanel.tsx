import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { CopilotChat } from "../types";
import CameraCapture from "./CameraCapture";
import { IconCamera, IconClose, IconImage, IconMic, IconSend, IconSpark, IconSpeaker, IconSpeakerOff, IconStop } from "./Icons";
import { shrinkImage } from "./imageUtil";
import { errText } from "./ui";
import { useVoice, voiceSupport } from "./useVoice";

interface Msg { id: number; role: "user" | "assistant"; text: string; image?: string; source?: CopilotChat["source"] }
interface Ctx { mode: "build" | "general"; title: string | null; step: number | null; total: number | null }

const LANG = "en-IN";

export default function CopilotPanel({ open, onOpen, onClose, userName }: {
  open: boolean; onOpen: () => void; onClose: () => void; userName: string;
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [image, setImage] = useState<{ file: File; url: string } | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [handsFree, setHandsFree] = useState(false);
  const [speakReplies, setSpeakReplies] = useState(true);
  const [ctx, setCtx] = useState<Ctx>({ mode: "general", title: null, step: null, total: null });

  // Latest values for callbacks fired by the speech APIs.
  const msgsRef = useRef(msgs); msgsRef.current = msgs;
  const imageRef = useRef(image); imageRef.current = image;
  const busyRef = useRef(busy); busyRef.current = busy;
  const handsFreeRef = useRef(handsFree); handsFreeRef.current = handsFree;
  const speakRef = useRef(speakReplies); speakRef.current = speakReplies;
  const openRef = useRef(open); openRef.current = open;
  const sendRef = useRef<(t: string) => void>(() => undefined);
  const voiceRef = useRef<ReturnType<typeof useVoice> | null>(null);
  const silences = useRef(0);
  const idRef = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const voice = useVoice({
    lang: LANG,
    onText: (t) => { silences.current = 0; sendRef.current(t); },
    onSilence: () => {
      if (!handsFreeRef.current) return;
      silences.current += 1;
      if (silences.current >= 2) {
        setHandsFree(false); silences.current = 0;
        setError("Voice chat paused because I didn’t hear anything. Tap Voice chat to continue.");
      } else voiceRef.current?.startListening();
    },
    onError: (m) => { setHandsFree(false); setError(m); },
  });
  voiceRef.current = voice;

  const refreshContext = useCallback(async () => {
    try {
      const b = await api.currentBuild();
      setCtx({ mode: "build", title: b.title, step: b.step.index + 1, total: b.total_steps });
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setCtx({ mode: "general", title: null, step: null, total: null });
    }
  }, []);

  useEffect(() => { if (open) refreshContext(); }, [open, refreshContext]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, busy, open]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const close = () => {
    setHandsFree(false); voice.stopListening(); voice.stopSpeaking(); setCameraOpen(false);
    onClose();
  };

  const setPhoto = async (file: File | null) => {
    if (!file) return;
    const small = await shrinkImage(file);
    setImage((old) => { if (old) URL.revokeObjectURL(old.url); return { file: small, url: URL.createObjectURL(small) }; });
    setCameraOpen(false); setError(null);
  };
  const clearPhoto = () => setImage((old) => { if (old) URL.revokeObjectURL(old.url); return null; });

  const send = async (raw: string) => {
    const q = raw.trim();
    const img = imageRef.current;
    if ((!q && !img) || busyRef.current) return;
    voice.stopSpeaking(); setError(null);
    const history = msgsRef.current.slice(-6).map((m) => ({ role: m.role, content: m.text }));
    setMsgs((m) => [...m, { id: ++idRef.current, role: "user", text: q || "Photo attached", image: img?.url }]);
    setInput(""); setImage(null); setBusy(true);
    try {
      const r = await api.copilotChat(q, history, img?.file);
      setCtx({ mode: r.mode, title: r.project_title, step: r.step_index !== null ? r.step_index + 1 : null, total: r.total_steps });
      setMsgs((m) => [...m, { id: ++idRef.current, role: "assistant", text: r.answer, source: r.source }]);
      const again = () => { if (handsFreeRef.current && openRef.current) voice.startListening(); };
      if ((speakRef.current || handsFreeRef.current) && voiceSupport.tts) voice.speak(r.answer, again); else again();
    } catch (e) {
      setHandsFree(false); setError(errText(e));
    } finally { setBusy(false); }
  };
  sendRef.current = send;

  const toggleHandsFree = () => {
    if (handsFree) { setHandsFree(false); voice.stopListening(); voice.stopSpeaking(); return; }
    silences.current = 0; setError(null);
    if (voice.startListening()) setHandsFree(true);
  };
  const pushToTalk = () => { if (voice.listening) voice.stopListening(); else voice.startListening(); };

  const first = userName.split(" ")[0] || "there";
  const status = voice.listening ? "Listening… speak now" : busy ? "Thinking…" : voice.speaking ? "Speaking… tap to stop" : null;
  const quick = ctx.mode === "build"
    ? ["Explain this step simply", "What can go wrong here?", "Which parts do I use for this step?"]
    : ["What can I build with my parts?", "How do I read resistor colour bands?", "Which of my parts should I test first?"];

  return (
    <>
      {!open && (
        <button onClick={onOpen} aria-label="Open the AI copilot"
          className="fixed bottom-24 right-4 z-40 flex items-center gap-2 rounded-full bg-ink px-4 py-3 text-sm font-medium text-white shadow-lg ring-2 ring-gold/70 transition hover:bg-emerald-800 lg:bottom-6 lg:right-6">
          <IconSpark size={18} className="text-gold-soft" /> Copilot
        </button>
      )}

      <aside aria-hidden={!open} aria-label="AI copilot"
        className={`fixed inset-0 z-50 flex flex-col bg-stone-50 shadow-2xl transition-transform duration-200 sm:inset-y-0 sm:left-auto sm:right-0 sm:w-[430px] sm:border-l sm:border-stone-200 ${open ? "translate-x-0" : "invisible translate-x-full"}`}>
        <header className="flex items-start gap-2 bg-ink px-4 py-3 text-white">
          <div className="min-w-0 flex-1">
            <h2 className="flex items-center gap-2 font-display text-lg font-bold"><IconSpark size={18} className="text-gold-soft" /> Copilot</h2>
            <p className="truncate text-xs text-emerald-100">
              {ctx.mode === "build" ? `Helping with ${ctx.title} · step ${ctx.step} of ${ctx.total}` : "General help · knows your parts"}
            </p>
          </div>
          <button onClick={() => setSpeakReplies((v) => !v)} aria-pressed={speakReplies} title={speakReplies ? "Replies are read aloud" : "Replies are silent"}
            className="grid h-9 w-9 place-items-center rounded-full hover:bg-white/10">
            {speakReplies ? <IconSpeaker size={18} /> : <IconSpeakerOff size={18} />}
            <span className="sr-only">{speakReplies ? "Mute replies" : "Read replies aloud"}</span>
          </button>
          <button onClick={close} aria-label="Close copilot" className="grid h-9 w-9 place-items-center rounded-full hover:bg-white/10"><IconClose size={18} /></button>
        </header>

        <div className="flex items-center gap-2 border-b border-stone-200 bg-white px-4 py-2">
          <button onClick={toggleHandsFree} aria-pressed={handsFree} disabled={!voiceSupport.stt}
            className={`btn !px-3 !py-1.5 text-xs ${handsFree ? "bg-gold text-white hover:bg-gold" : "border border-stone-300 bg-white text-stone-800 hover:bg-stone-100"}`}>
            <IconMic size={14} /> {handsFree ? "Voice chat on · tap to end" : "Start voice chat"}
          </button>
          <p className="min-w-0 flex-1 truncate text-xs text-stone-500" aria-live="polite">
            {voiceSupport.stt ? (status ?? "Talk, type, or add a photo") : "Voice input needs Chrome or Edge. Typing works everywhere."}
          </p>
          {voice.speaking && <button className="btn-ghost !px-2 !py-1 text-xs" onClick={voice.stopSpeaking}><IconStop size={14} /> Stop</button>}
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {msgs.length === 0 && (
            <div className="space-y-3">
              <p className="text-sm text-stone-700">
                Hi {first}. Ask about your parts, a wiring problem or a build. Add a photo and I’ll look at it, or start a voice chat and just talk.
              </p>
              <div className="flex flex-wrap gap-2">
                {quick.map((q) => (
                  <button key={q} className="rounded-full border border-stone-300 bg-white px-3 py-1.5 text-xs text-stone-800 hover:bg-stone-100" onClick={() => send(q)}>{q}</button>
                ))}
              </div>
            </div>
          )}
          {msgs.map((m) => (
            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"} animate-rise`}>
              <div className={`max-w-[88%] rounded-2xl px-3 py-2 text-sm ${m.role === "user" ? "bg-emerald-600 text-white" : "border border-stone-200 bg-white text-stone-800"}`}>
                {m.image && <img src={m.image} alt="Photo you sent" className="mb-2 max-h-40 rounded-lg" />}
                <p className="whitespace-pre-wrap">{m.text}</p>
                {m.role === "assistant" && (
                  <div className="mt-1 flex items-center gap-2 text-xs text-stone-500">
                    {voiceSupport.tts && <button className="inline-flex items-center gap-1 hover:text-stone-800" onClick={() => voice.speak(m.text)}><IconSpeaker size={13} /> Read aloud</button>}
                    {m.source === "fallback" && <span>Using fallback response</span>}
                    {m.source === "safety_guard" && <span className="text-red-700">Safety message</span>}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && <p className="text-sm text-stone-500">Thinking…</p>}
          {voice.interim && <p className="text-right text-sm italic text-stone-500">{voice.interim}</p>}
          <div ref={endRef} />
        </div>

        <div className="space-y-2 border-t border-stone-200 bg-white px-4 py-3">
          {error && <div role="alert" className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">{error}</div>}
          {cameraOpen && <CameraCapture onCapture={setPhoto} onClose={() => setCameraOpen(false)} hint="Show the part or your wiring clearly." />}
          {image && (
            <div className="flex items-center gap-2">
              <img src={image.url} alt="Photo to send" className="h-14 w-14 rounded-lg object-cover" />
              <p className="flex-1 text-xs text-stone-600">Photo ready. Add a question or just send it.</p>
              <button onClick={clearPhoto} aria-label="Remove photo" className="grid h-8 w-8 place-items-center rounded-full hover:bg-stone-100"><IconClose size={16} /></button>
            </div>
          )}
          <div className="flex items-end gap-1.5">
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
              onChange={(e) => { setPhoto(e.target.files?.[0] ?? null); e.target.value = ""; }} />
            <button className="btn-ghost !px-2.5" onClick={() => fileRef.current?.click()} aria-label="Attach a photo"><IconImage size={18} /></button>
            <button className="btn-ghost !px-2.5" onClick={() => setCameraOpen((v) => !v)} aria-label="Use the camera" aria-pressed={cameraOpen}><IconCamera size={18} /></button>
            <textarea className="input max-h-28 min-h-[40px] flex-1 resize-none" rows={1} maxLength={500} value={input}
              placeholder={image ? "Ask about this photo…" : "Ask anything about your parts or build"}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }} />
            <button className={`btn !px-2.5 ${voice.listening ? "bg-gold text-white hover:bg-gold" : "border border-stone-300 bg-white text-stone-800 hover:bg-stone-100"}`}
              onClick={pushToTalk} disabled={!voiceSupport.stt || handsFree} aria-label={voice.listening ? "Stop listening" : "Speak one question"} aria-pressed={voice.listening}>
              <IconMic size={18} />
            </button>
            <button className="btn-primary !px-2.5" onClick={() => send(input)} disabled={busy || (!input.trim() && !image)} aria-label="Send"><IconSend size={18} /></button>
          </div>
          <p className="text-[11px] leading-snug text-stone-500">
            Copilot can’t test your parts and can be wrong. Check with a multimeter when unsure, and disconnect power before changing wires.
          </p>
        </div>
      </aside>
    </>
  );
}

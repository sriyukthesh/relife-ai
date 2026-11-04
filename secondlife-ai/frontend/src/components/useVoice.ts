import { useCallback, useEffect, useRef, useState } from "react";

// Browser speech recognition (Chrome/Edge/Safari). This is NOT Muse Voice Transcribe.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const Recognition: any = (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;

export const voiceSupport = {
  stt: Boolean(Recognition),
  tts: typeof window !== "undefined" && "speechSynthesis" in window,
};

interface Options {
  lang?: string;
  /** Called once with the final transcript when the user stops talking. */
  onText: (text: string) => void;
  /** Called when listening ended without any speech ("no-speech"). */
  onSilence?: () => void;
  onError: (message: string) => void;
}

/** Split text into short chunks; some browsers cut off long utterances. */
export function chunkForSpeech(text: string, max = 180): string[] {
  const sentences = text.replace(/\s+/g, " ").trim().match(/[^.!?]+[.!?]*\s*/g) ?? [];
  const out: string[] = [];
  let cur = "";
  for (const s of sentences) {
    if ((cur + s).length > max && cur) { out.push(cur.trim()); cur = s; } else cur += s;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}

export function useVoice({ lang = "en-IN", onText, onSilence, onError }: Options) {
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [interim, setInterim] = useState("");
  const recRef = useRef<any>(null); // eslint-disable-line @typescript-eslint/no-explicit-any
  const speakToken = useRef(0);
  const cb = useRef({ onText, onSilence, onError });
  cb.current = { onText, onSilence, onError };

  const stopSpeaking = useCallback(() => {
    speakToken.current += 1; // invalidates pending onend handlers
    if (voiceSupport.tts) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  const speak = useCallback((text: string, onDone?: () => void) => {
    if (!voiceSupport.tts || !text.trim()) { onDone?.(); return; }
    window.speechSynthesis.cancel();
    const token = ++speakToken.current;
    const chunks = chunkForSpeech(text);
    const voices = window.speechSynthesis.getVoices();
    const voice = voices.find((v) => v.lang === lang) ?? voices.find((v) => v.lang.startsWith(lang.split("-")[0]));
    setSpeaking(true);
    chunks.forEach((c, i) => {
      const u = new SpeechSynthesisUtterance(c);
      u.lang = lang; u.rate = 0.98;
      if (voice) u.voice = voice;
      const finish = () => {
        if (token !== speakToken.current) return;
        if (i === chunks.length - 1) { setSpeaking(false); onDone?.(); }
      };
      u.onend = finish;
      u.onerror = finish;
      window.speechSynthesis.speak(u);
    });
  }, [lang]);

  const stopListening = useCallback(() => {
    const r = recRef.current;
    if (r) { r.__stopped = true; try { r.stop(); } catch { /* already stopped */ } }
  }, []);

  const startListening = useCallback((): boolean => {
    if (!Recognition) {
      cb.current.onError("Voice input isn’t supported in this browser. Use Chrome or Edge, or type your question.");
      return false;
    }
    if (recRef.current) return true;
    stopSpeaking();
    const r = new Recognition();
    r.lang = lang; r.interimResults = true; r.continuous = false; r.maxAlternatives = 1;
    let finalText = "";
    let err = "";
    r.onstart = () => setListening(true);
    r.onresult = (ev: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      let live = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const res = ev.results[i];
        if (res.isFinal) finalText += res[0].transcript; else live += res[0].transcript;
      }
      setInterim((finalText + live).trim());
    };
    r.onerror = (ev: any) => { err = ev.error ?? ""; }; // eslint-disable-line @typescript-eslint/no-explicit-any
    r.onend = () => {
      setListening(false); setInterim("");
      const stopped = r.__stopped === true;
      recRef.current = null;
      if (finalText.trim()) { cb.current.onText(finalText.trim()); return; }
      if (err === "not-allowed" || err === "service-not-allowed") {
        cb.current.onError("Microphone permission is blocked. Allow it in your browser’s site settings, or type instead.");
      } else if (err === "audio-capture") {
        cb.current.onError("No microphone found.");
      } else if (err === "network") {
        cb.current.onError("Speech recognition needs an internet connection in this browser.");
      } else if (!stopped) {
        cb.current.onSilence?.();
      }
    };
    recRef.current = r;
    try { r.start(); } catch { recRef.current = null; return false; }
    return true;
  }, [lang, stopSpeaking]);

  useEffect(() => () => {
    stopListening();
    if (voiceSupport.tts) window.speechSynthesis.cancel();
  }, [stopListening]);

  return { listening, speaking, interim, startListening, stopListening, speak, stopSpeaking };
}

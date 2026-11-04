import { useCallback, useEffect, useRef, useState } from "react";
import { IconCamera, IconClose, IconSwap } from "./Icons";

interface Props {
  onCapture: (file: File) => void;
  onClose?: () => void;
  /** Short line shown under the viewfinder. */
  hint?: string;
}

type Light = "ok" | "dark" | "bright";

/** Live viewfinder (getUserMedia). Needs https or localhost. Captures one JPEG frame. */
export default function CameraCapture({ onCapture, onClose, hint }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [facing, setFacing] = useState<"environment" | "user">("environment");
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [light, setLight] = useState<Light>("ok");
  const [canSwitch, setCanSwitch] = useState(false);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => {
    let cancelled = false;
    setReady(false); setError(null);
    if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) {
      setError("Live camera needs https or localhost. Use “Upload photo” instead.");
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: facing }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
      .then(async (stream) => {
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        stop();
        streamRef.current = stream;
        const v = videoRef.current;
        if (v) { v.srcObject = stream; await v.play().catch(() => undefined); }
        setReady(true);
        const cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
        if (!cancelled) setCanSwitch(cams.length > 1);
      })
      .catch((e: DOMException) => {
        if (cancelled) return;
        setError(
          e.name === "NotAllowedError" ? "Camera permission is blocked. Allow it in your browser’s site settings, or upload a photo."
          : e.name === "NotFoundError" ? "No camera found on this device. Upload a photo instead."
          : "The camera could not start. Close other apps using it, or upload a photo.",
        );
      });
    return () => { cancelled = true; stop(); };
  }, [facing, stop]);

  // Lighting guidance: sample a tiny frame twice a second and look at average brightness.
  useEffect(() => {
    if (!ready) return;
    const c = document.createElement("canvas");
    c.width = 48; c.height = 36;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    const id = window.setInterval(() => {
      const v = videoRef.current;
      if (!ctx || !v || v.videoWidth === 0) return;
      ctx.drawImage(v, 0, 0, c.width, c.height);
      const d = ctx.getImageData(0, 0, c.width, c.height).data;
      let sum = 0;
      for (let i = 0; i < d.length; i += 4) sum += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
      const mean = sum / (d.length / 4);
      setLight(mean < 45 ? "dark" : mean > 225 ? "bright" : "ok");
    }, 500);
    return () => window.clearInterval(id);
  }, [ready]);

  const capture = () => {
    const v = videoRef.current;
    if (!v || v.videoWidth === 0) return;
    const c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d")?.drawImage(v, 0, 0);
    c.toBlob((b) => {
      if (b) onCapture(new File([b], `capture-${Date.now()}.jpg`, { type: "image/jpeg" }));
    }, "image/jpeg", 0.92);
  };

  if (error) {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900" role="alert">
        {error}
        {onClose && <button className="btn-ghost mt-3 w-full" onClick={onClose}>Close camera</button>}
      </div>
    );
  }

  const msg = light === "dark" ? "Too dark. Add light or move closer to a lamp."
    : light === "bright" ? "Too bright or glare. Tilt the parts away from the light."
    : hint ?? "Lay parts on a plain surface and fill the frame.";

  return (
    <div className="overflow-hidden rounded-xl bg-black">
      <div className="relative aspect-[4/3] w-full">
        <video ref={videoRef} playsInline muted autoPlay className="h-full w-full object-cover" />
        {/* framing corners */}
        <div className="pointer-events-none absolute inset-6 rounded-lg border border-white/25" />
        {(["left-4 top-4 border-l-2 border-t-2", "right-4 top-4 border-r-2 border-t-2", "left-4 bottom-4 border-b-2 border-l-2", "right-4 bottom-4 border-b-2 border-r-2"]).map((c) => (
          <span key={c} className={`pointer-events-none absolute h-6 w-6 border-gold ${c}`} />
        ))}
        {!ready && <p className="absolute inset-0 grid place-items-center text-sm text-white/80">Starting camera…</p>}
        {onClose && (
          <button onClick={onClose} aria-label="Close camera" className="absolute right-3 top-3 grid h-9 w-9 place-items-center rounded-full bg-black/55 text-white hover:bg-black/75">
            <IconClose size={18} />
          </button>
        )}
      </div>
      <div className="flex items-center gap-3 bg-ink px-4 py-3">
        <p className={`min-w-0 flex-1 text-xs ${light === "ok" ? "text-emerald-100" : "text-gold-soft"}`} aria-live="polite">{msg}</p>
        {canSwitch && (
          <button onClick={() => setFacing((f) => (f === "environment" ? "user" : "environment"))} aria-label="Switch camera"
            className="grid h-10 w-10 place-items-center rounded-full border border-white/25 text-white hover:bg-white/10">
            <IconSwap size={18} />
          </button>
        )}
        <button onClick={capture} disabled={!ready} aria-label="Take photo"
          className="grid h-14 w-14 place-items-center rounded-full border-4 border-gold-soft bg-white text-ink transition active:scale-95 disabled:opacity-50">
          <IconCamera size={22} />
        </button>
      </div>
    </div>
  );
}

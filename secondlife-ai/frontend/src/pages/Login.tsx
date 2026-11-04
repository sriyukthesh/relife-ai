import { useState } from "react";
import { api, setToken } from "../api";
import { BrandMark } from "../components/Icons";
import { errText, ErrorBanner } from "../components/ui";
import type { User } from "../types";

export default function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("demo@secondlife.ai");
  const [password, setPassword] = useState("demo1234");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true); setError(null);
    try {
      const t = mode === "login" ? await api.login(email, password) : await api.register(email, name || "Maker", password);
      setToken(t.access_token);
      onLogin(t.user);
    } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-ink p-12 text-white lg:flex">
        <div className="flex items-center gap-3"><BrandMark size={36} /><span className="font-display text-xl font-bold">ReLife AI</span></div>
        <div>
          <h1 className="font-display text-5xl font-bold leading-tight">Build projects. Give used components a new life.</h1>
          <p className="mt-4 max-w-md text-emerald-100/80">Get guided help making projects, and buy or sell used electronic and electrical components in the marketplace.</p>
        </div>
        <div />
      </div>
      <div className="flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-6 flex items-center gap-2 lg:hidden"><BrandMark /><span className="font-display text-xl font-bold">ReLife AI</span></div>
          <h2 className="font-display text-2xl font-bold">{mode === "login" ? "Log in" : "Create your account"}</h2>
          <p className="mb-2 mt-1 text-sm text-stone-600">{mode === "login" ? "Welcome back. Your dashboard is waiting." : "It takes a few seconds."}</p>
          <p className="mb-5 text-sm text-stone-600">Build projects with guided help, and buy or sell used electronic and electrical components.</p>
          <div className="space-y-3">
            <ErrorBanner message={error} />
            {mode === "register" && <input className="input" placeholder="Your name" aria-label="Your name" value={name} onChange={(e) => setName(e.target.value)} />}
            <input className="input" type="email" placeholder="Email" aria-label="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <input className="input" type="password" placeholder="Password (8+ characters)" aria-label="Password" value={password}
              onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
            <button className="btn-primary w-full" disabled={busy} onClick={submit}>{busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}</button>
            <button className="w-full text-sm text-stone-600 underline" onClick={() => setMode(mode === "login" ? "register" : "login")}>
              {mode === "login" ? "New here? Create an account" : "Have an account? Log in"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

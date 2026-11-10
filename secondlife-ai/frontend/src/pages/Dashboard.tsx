import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../api";
import { CategoryBars, WeeklyBars } from "../components/Charts";
import { num, dollars, timeAgo, weight } from "../components/format";
import { IconScan, IconSpark } from "../components/Icons";
import { errText, ErrorBanner } from "../components/ui";
import type { Tab } from "../nav";
import type { ImpactStats, Recommendations, User } from "../types";

/** Animates 0 -> value once (skipped when the user prefers reduced motion). */
function useCountUp(value: number, ms = 900): number {
  const [v, setV] = useState(0);
  const raf = useRef(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setV(value); return; }
    const t0 = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / ms);
      setV(value * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [value, ms]);
  return v;
}

function Stage({ label, value, format, sub }: { label: string; value: number; format: (n: number) => string; sub: string }) {
  const shown = useCountUp(value);
  return (
    <li className="relative pl-7 lg:pl-0 lg:pt-8">
      <span aria-hidden className="absolute -left-[9px] top-1 h-[18px] w-[18px] rounded-full bg-gold ring-4 ring-ink lg:left-0 lg:top-0" />
      <p className="font-display text-4xl font-bold leading-none tnum sm:text-5xl">{format(Math.round(shown))}</p>
      <p className="mt-2 text-sm font-medium text-white">{label}</p>
      <p className="mt-0.5 text-xs text-emerald-100/80">{sub}</p>
    </li>
  );
}

function Section({ title, aside, children }: { title: string; aside?: string; children: ReactNode }) {
  return (
    <section className="border-t-2 border-ink pt-3">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="font-display text-lg font-bold">{title}</h2>
        {aside && <span className="text-xs text-stone-500">{aside}</span>}
      </div>
      {children}
    </section>
  );
}

const greet = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"; };

export default function Dashboard({ user, onNavigate, onOpenCopilot }: {
  user: User; onNavigate: (t: Tab) => void; onOpenCopilot: () => void;
}) {
  const [stats, setStats] = useState<ImpactStats | null>(null);
  const [recs, setRecs] = useState<Recommendations | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try { setStats(await api.stats()); } catch (e) { setError(errText(e)); }
    api.recommendations().then(setRecs).catch(() => setRecs(null));
  }, []);
  useEffect(() => { load(); }, [load]);

  const first = user.name.split(" ")[0];

  if (error) {
    return (
      <div className="space-y-3">
        <ErrorBanner message={error} />
        <button className="btn-primary" onClick={load}>Try again</button>
      </div>
    );
  }
  if (!stats) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
        <div className="h-9 w-64 animate-pulse rounded bg-stone-200" />
        <div className="h-56 animate-pulse rounded-2xl bg-stone-200" />
        <div className="grid gap-6 lg:grid-cols-3"><div className="h-64 animate-pulse rounded bg-stone-200 lg:col-span-2" /><div className="h-64 animate-pulse rounded bg-stone-200" /></div>
      </div>
    );
  }

  const p = stats.platform, me = stats.me;
  const ready = recs?.matches.filter((m) => m.can_build).length ?? 0;
  const near = recs?.matches.filter((m) => !m.can_build && m.coverage >= 0.6).length ?? 0;
  const empty = p.parts_reused + p.parts_resold === 0;

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">{greet()}, {first}</h1>
          <p className="mt-1 text-sm text-stone-600">What makers on ReLife AI have kept out of the bin, and what you can do next.</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-stone-500">
          {stats.demo_data && (
            <span className="badge bg-gold-soft text-gold" title="This server contains seeded demo accounts. Treat these totals as demo data, not real usage.">Includes demo accounts</span>
          )}
          <span>Updated {timeAgo(stats.generated_at)}</span>
        </div>
      </header>

      {/* The loop: the product's story as one trace, left to right. */}
      <section aria-labelledby="loop-h" className="rounded-2xl bg-ink px-6 py-7 text-white lg:px-8">
        <h2 id="loop-h" className="font-display text-xl font-bold">Parts kept in the loop</h2>
        <p className="mt-1 max-w-xl text-sm text-emerald-100/80">Every part that is reused or resold is one less in a drawer, or in the bin.</p>
        <ol className="relative mt-7 ml-2 grid gap-8 border-l border-gold/50 lg:ml-0 lg:grid-cols-4 lg:gap-6 lg:border-l-0">
          <div aria-hidden className="absolute left-0 right-0 top-[9px] hidden h-px bg-gold/50 lg:block" />
          <Stage label="Parts in circulation now" value={p.parts_in_circulation} format={num}
            sub={`${num(p.active_listings)} listings open · ${num(p.makers)} makers`} />
          <Stage label="Reused in finished builds" value={p.parts_reused} format={num}
            sub={`${num(p.builds_completed)} builds completed`} />
          <Stage label="Resold to other makers" value={p.parts_resold} format={num}
            sub={`${dollars(p.marketplace_volume_cents)} traded`} />
          <Stage label="E-waste kept out of the bin" value={p.diverted_g_low} format={weight}
            sub={`Estimate: ${weight(p.diverted_g_low)} to ${weight(p.diverted_g_high)}`} />
        </ol>
        {empty && <p className="mt-6 text-sm text-gold-soft">No finished builds or sales yet. Finish a guided build or sell a part and this board will start counting.</p>}
      </section>

      <div className="grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Section title="Parts given a second life, by week" aside="Last 12 weeks">
            <WeeklyBars data={stats.weekly} />
            <div className="mt-2 flex gap-4 text-xs text-stone-600">
              <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-sm bg-emerald-600" /> Reused in builds</span>
              <span className="flex items-center gap-1.5"><i className="inline-block h-2.5 w-2.5 rounded-sm bg-gold" /> Resold</span>
            </div>
          </Section>
        </div>
        <Section title="Where the weight comes from" aside="Estimated">
          {stats.by_category.length ? <CategoryBars rows={stats.by_category} format={weight} /> : <p className="text-sm text-stone-600">Nothing counted yet.</p>}
        </Section>
      </div>

      <div className="grid gap-8 lg:grid-cols-3">
        <Section title="Your impact">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-4">
            {[
              ["Parts you reused", num(me.parts_reused)],
              ["Parts you sold", num(me.parts_resold)],
              ["Parts you bought", num(me.parts_bought)],
              ["Builds finished", num(me.builds_completed)],
              ["E-waste kept out", weight(me.diverted_g_low)],
              ["Parts in your stock", num(me.parts_in_stock)],
            ].map(([k, v]) => (
              <div key={k}><dt className="text-xs text-stone-500">{k}</dt><dd className="font-display text-2xl font-bold tnum">{v}</dd></div>
            ))}
          </dl>
          <div className="mt-5 flex flex-wrap gap-2">
            <button className="btn-primary" onClick={() => onNavigate("scan")}><IconScan size={16} /> Scan parts</button>
            <button className="btn-ghost" onClick={() => onNavigate("recommend")}>
              {ready > 0 ? `${ready} project${ready > 1 ? "s" : ""} ready to build` : near > 0 ? `${near} project${near > 1 ? "s" : ""} almost ready` : "See project ideas"}
            </button>
            <button className="btn-ghost" onClick={onOpenCopilot}><IconSpark size={16} /> Ask Copilot</button>
          </div>
        </Section>

        <Section title="Community right now">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-4">
            {[
              ["Makers", num(p.makers)],
              ["Open listings", num(p.active_listings)],
              ["Builds finished", num(p.builds_completed)],
              ["Traded", dollars(p.marketplace_volume_cents)],
            ].map(([k, v]) => (
              <div key={k}><dt className="text-xs text-stone-500">{k}</dt><dd className="font-display text-2xl font-bold tnum">{v}</dd></div>
            ))}
          </dl>
        </Section>

        <Section title="Recent activity">
          {stats.activity.length === 0 ? <p className="text-sm text-stone-600">Nothing yet. Be the first to list a part.</p> : (
            <ul className="space-y-3">
              {stats.activity.map((a, i) => (
                <li key={i} className="flex gap-3 text-sm">
                  <span aria-hidden className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${a.kind === "build" ? "bg-emerald-600" : a.kind === "purchase" ? "bg-gold" : "bg-slate2"}`} />
                  <div className="min-w-0"><p className={a.mine ? "font-medium" : ""}>{a.text}</p><p className="text-xs text-stone-500">{timeAgo(a.when)}</p></div>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      <details className="border-t-2 border-ink pt-3 text-sm text-stone-700">
        <summary className="cursor-pointer font-display text-lg font-bold">How these numbers are worked out</summary>
        <ul className="mt-3 list-disc space-y-1.5 pl-5">{stats.methodology.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        <p className="mt-4 text-xs font-medium text-stone-600">Assumed mass per part</p>
        <ul className="mt-1 grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-3">
          {stats.methodology.grams_per_part.map((g) => <li key={g.category} className="flex justify-between border-b border-stone-200 py-1"><span>{g.label}</span><span className="tnum">{g.grams} g</span></li>)}
        </ul>
      </details>
    </div>
  );
}

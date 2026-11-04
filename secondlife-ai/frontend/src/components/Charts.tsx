import type { ImpactStats } from "../types";

const shortDate = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

/** Stacked weekly bars: reused (green) + resold (gold). Plain SVG, scales to its container. */
export function WeeklyBars({ data }: { data: ImpactStats["weekly"] }) {
  const W = 640, H = 220, padL = 34, padB = 26, padT = 10, padR = 8;
  const max = Math.max(5, ...data.map((d) => d.reused + d.resold));
  const top = Math.ceil(max / 5) * 5;
  const bw = (W - padL - padR) / data.length;
  const y = (v: number) => padT + (H - padT - padB) * (1 - v / top);
  const total = data.reduce((s, d) => s + d.reused + d.resold, 0);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" className="w-full"
      aria-label={`Parts reused and resold per week over the last ${data.length} weeks, ${total} in total`}>
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <line x1={padL} x2={W - padR} y1={y(top * t)} y2={y(top * t)} className="stroke-stone-200" strokeWidth={1} />
          <text x={padL - 6} y={y(top * t) + 4} textAnchor="end" className="fill-stone-500 tnum" fontSize={11}>{Math.round(top * t)}</text>
        </g>
      ))}
      {data.map((d, i) => {
        const x = padL + i * bw + bw * 0.16, w = bw * 0.68;
        const yr = y(d.reused), yt = y(d.reused + d.resold);
        return (
          <g key={d.week_start}>
            <title>{`Week of ${shortDate(d.week_start)}: ${d.reused} reused, ${d.resold} resold`}</title>
            <rect x={x} y={yr} width={w} height={Math.max(0, y(0) - yr)} rx={2} className="fill-emerald-600" />
            <rect x={x} y={yt} width={w} height={Math.max(0, yr - yt)} rx={2} className="fill-gold" />
            {(i === 0 || i === data.length - 1 || i === Math.floor(data.length / 2)) && (
              <text x={x + w / 2} y={H - 8} textAnchor="middle" className="fill-stone-500" fontSize={11}>{shortDate(d.week_start)}</text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/** Horizontal bars for the categories that contribute most weight. */
export function CategoryBars({ rows, format }: { rows: ImpactStats["by_category"]; format: (g: number) => string }) {
  const max = Math.max(1, ...rows.map((r) => r.grams_low));
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.category}>
          <div className="flex items-baseline justify-between text-sm">
            <span className="text-stone-800">{r.label}</span>
            <span className="tnum text-stone-600">{format(r.grams_low)}</span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-stone-100" role="presentation">
            <div className="h-full rounded-full bg-emerald-600" style={{ width: `${Math.max(4, (r.grams_low / max) * 100)}%` }} />
          </div>
          <p className="mt-0.5 text-xs text-stone-500 tnum">{r.reused} reused · {r.resold} resold</p>
        </li>
      ))}
    </ul>
  );
}

export const num = (n: number) => n.toLocaleString("en-IN");

export function weight(g: number): string {
  if (g < 1000) return `${Math.round(g)} g`;
  const kg = g / 1000;
  return `${kg.toLocaleString("en-IN", { maximumFractionDigits: kg < 10 ? 2 : 1 })} kg`;
}

export function rupees(paise: number): string {
  return `₹${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

export function timeAgo(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.round(h / 24);
  return d === 1 ? "yesterday" : `${d} days ago`;
}

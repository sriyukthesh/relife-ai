import type {
  Build, Catalog, CopilotAnswer, CopilotChat, ImpactStats, InspectResponse, InventoryIn, InventoryItem, Listing,
  ListingSuggestion, Order, Address, CartLine, CartPreview, PayMethod, Payment, ProjectOffers, Recommendations, Token, User, Condition, Specs,
  TeardownAssessment, TestProcedure, ComponentTestResult, ResistorOption, LedResistorResult, BuildPhotoCheck,
} from "./types";

const BASE: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
let token: string | null = localStorage.getItem("sl_token");

export function setToken(t: string | null) {
  token = t;
  if (t) localStorage.setItem("sl_token", t);
  else localStorage.removeItem("sl_token");
}
export const hasToken = () => token !== null;

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail : (detail as { message?: string })?.message ?? `HTTP ${status}`);
  }
}

async function req<T>(path: string, init: { method?: string; json?: unknown; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (init.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(init.json); }
  if (init.form) body = init.form;
  let res: Response;
  try {
    res = await fetch(BASE + path, { method: init.method ?? "GET", headers, body });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }
  if (res.status === 401) { setToken(null); }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data?.detail ?? `HTTP ${res.status}`);
  return data as T;
}

export const api = {
  login: (email: string, password: string) => req<Token>("/auth/login", { method: "POST", json: { email, password } }),
  register: (email: string, name: string, password: string) => req<Token>("/auth/register", { method: "POST", json: { email, name, password } }),
  me: () => req<User>("/auth/me"),
  catalog: () => req<Catalog>("/catalog"),

  inspect: (file: File) => { const f = new FormData(); f.append("file", file); return req<InspectResponse>("/inspect", { method: "POST", form: f }); },
  teardown: (file: File, deviceName: string) => {
    const f = new FormData();
    f.append("file", file);
    f.append("device_name", deviceName);
    return req<TeardownAssessment>("/teardown", { method: "POST", form: f });
  },

  inventory: () => req<InventoryItem[]>("/inventory"),
  addItem: (body: InventoryIn) => req<InventoryItem>("/inventory", { method: "POST", json: body }),
  patchItem: (id: number, body: { quantity?: number; condition?: Condition; specs?: Specs; label?: string }) =>
    req<InventoryItem>(`/inventory/${id}`, { method: "PATCH", json: body }),
  deleteItem: (id: number) => req<void>(`/inventory/${id}`, { method: "DELETE" }),
  resistorSubstitutes: (targetOhm: number, tolerance = 0.1) =>
    req<{ target_ohm: number; options: ResistorOption[] }>(
      `/substitutions/resistor?target_ohm=${encodeURIComponent(targetOhm)}&tolerance=${encodeURIComponent(tolerance)}`,
    ),
  ledResistor: (supplyV: number, ledVf: number, currentMa: number) =>
    req<LedResistorResult>(
      `/substitutions/led-resistor?supply_v=${encodeURIComponent(supplyV)}&led_vf=${encodeURIComponent(ledVf)}&current_ma=${encodeURIComponent(currentMa)}`,
    ),
  testProcedure: (category: string) => req<TestProcedure>(`/testing/procedure/${encodeURIComponent(category)}`),
  completeTest: (itemId: number, measurements: Record<string, number | boolean>) =>
    req<ComponentTestResult>(`/testing/${itemId}/complete`, {
      method: "POST",
      json: { measurements, confirmed_by_user: true },
    }),
  checkBuildPhoto: (buildId: number, file: File, note: string) => {
    const f = new FormData();
    f.append("file", file);
    f.append("note", note);
    return req<BuildPhotoCheck>(`/builds/${buildId}/check-photo`, { method: "POST", form: f });
  },

  recommendations: () => req<Recommendations>("/recommendations"),

  startBuild: (project_slug: string, allow_incomplete = false) => req<Build>("/builds", { method: "POST", json: { project_slug, allow_incomplete } }),
  currentBuild: () => req<Build>("/builds/current"),
  nextStep: (id: number) => req<Build>(`/builds/${id}/next`, { method: "POST" }),
  prevStep: (id: number) => req<Build>(`/builds/${id}/previous`, { method: "POST" }),
  finishBuild: (id: number) => req<Build>(`/builds/${id}/finish`, { method: "POST" }),
  ask: (build_id: number, question: string, history: { role: string; content: string }[]) =>
    req<CopilotAnswer>("/copilot/ask", { method: "POST", json: { build_id, question, history } }),

  stats: () => req<ImpactStats>("/stats/impact"),

  /** Global copilot: text and/or one photo; uses the active build as context when there is one. */
  copilotChat: (message: string, history: { role: string; content: string }[], image?: File | null) => {
    const f = new FormData();
    f.append("message", message);
    f.append("history", JSON.stringify(history));
    f.append("use_build", "true");
    if (image) f.append("image", image);
    return req<CopilotChat>("/copilot/chat", { method: "POST", form: f });
  },

  listings: (mine = false) => req<Listing[]>(`/marketplace/listings?mine=${mine}`),
  createListing: (item_id: number, quantity: number, price_cents: number, title?: string) =>
    req<Listing>("/marketplace/listings", { method: "POST", json: { item_id, quantity, price_cents, title } }),
  suggestListing: (item_id: number) => req<ListingSuggestion>(`/marketplace/suggest/${item_id}`),
  cancelListing: (id: number) => req<void>(`/marketplace/listings/${id}`, { method: "DELETE" }),
  buy: (id: number, quantity: number) => req<Order>(`/marketplace/listings/${id}/buy`, { method: "POST", json: { quantity } }),
  orders: () => req<Order[]>("/marketplace/orders"),

  // cart + checkout (only the method name is sent, never card details)
  checkoutPreview: (lines: CartLine[]) => req<CartPreview>("/checkout/preview", { method: "POST", json: { lines } }),
  pay: (p: { lines: CartLine[]; address: Address; method: PayMethod; idempotency_key: string; simulate_decline: boolean }) =>
    req<Payment>("/checkout/pay", { method: "POST", json: p }),
  payments: () => req<Payment[]>("/checkout/payments"),
  offersFor: (slug: string) => req<ProjectOffers>(`/marketplace/for-project/${slug}`),
};

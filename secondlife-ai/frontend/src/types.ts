export type Condition = "unverified" | "tested_ok" | "suspect_damaged";
export type Specs = Record<string, string | number>;

export interface User { id: number; email: string; name: string }
export interface Token { access_token: string; user: User }

export interface SpecField { label: string; unit: string | null; type: "number" | "text" | "choice"; choices?: string[] }
export interface Catalog {
  categories: Record<string, { label: string; required: string[] }>;
  spec_fields: Record<string, SpecField>;
  conditions: Condition[];
}

export interface Proposal {
  proposal_id: string; category: string; label: string; specs: Specs; quantity: number;
  suggested_condition: Condition; ai_confidence: number; needs_review: boolean;
  missing_required_specs: string[]; visible_markings: string; damage_flags: string[];
  uncertainties: string[]; evidence: string; box: number[] | null; box_source: string;
}
export interface InspectResponse {
  proposals: Proposal[]; segmentation_mode: string; image_width: number; image_height: number;
  notes: string[]; disclaimer: string;
}

export interface InventoryItem {
  id: number; category: string; label: string; specs: Specs; quantity: number;
  condition: Condition; source: string; ai_confidence: number | null; ai_notes: string | null;
  missing_specs: string[]; usable: boolean;
}
export interface InventoryIn {
  category: string; label: string; specs: Specs; quantity: number; condition: Condition;
  source: "scan" | "manual"; ai_confidence?: number | null; ai_notes?: string | null; confirmed_by_user: true;
}

export interface Allocation { item_id: number; label: string; quantity: number; condition: string }
export interface RequirementResult {
  index: number; label: string; category: string; needed: number; allocated: Allocation[];
  missing: number; status: "ok" | "partial" | "missing"; warnings: string[];
}
export interface MissingPart { label: string; category: string; quantity: number; constraints: Record<string, unknown> }
export interface ProjectMatch {
  project_id: number; slug: string; title: string; difficulty: number; estimated_minutes: number;
  description: string; can_build: boolean; coverage: number; requirements: RequirementResult[];
  missing_parts: MissingPart[]; warnings: string[];
}
export interface Recommendations { matches: ProjectMatch[]; excluded_items: { id: number; label: string; reason: string }[] }

export interface Build {
  id: number; project_slug: string; title: string; status: string; current_step: number;
  total_steps: number; step: { index: number; title: string; instruction: string };
  is_last: boolean; safety_note: string | null; warnings: string[]; missing_parts: MissingPart[];
}
export interface CopilotAnswer { answer: string; step_index: number; source: "ai" | "safety_guard" | "fallback" }

export interface Listing {
  id: number; seller_id: number; seller_name: string; category: string; label: string; specs: Specs;
  quantity: number; price_cents: number; condition: string; status: string; mine: boolean; created_at: string;
}
export interface Order { id: number; listing_id: number; label: string; quantity: number; total_cents: number; status: string; created_at: string; note: string }
export interface PartOffers { label: string; category: string; quantity: number; constraints: Record<string, unknown>; offers: Listing[] }
export interface ProjectOffers { project_slug: string; parts: PartOffers[] }

// ---- dashboard impact ----
export interface ImpactTotals { parts_reused: number; parts_resold: number; diverted_g_low: number; diverted_g_high: number }
export interface ImpactStats {
  generated_at: string;
  platform: ImpactTotals & {
    builds_completed: number; makers: number; parts_in_circulation: number;
    active_listings: number; marketplace_volume_paise: number;
  };
  me: ImpactTotals & { builds_completed: number; parts_in_stock: number; parts_bought: number; active_listings: number };
  weekly: { week_start: string; reused: number; resold: number }[];
  by_category: { category: string; label: string; reused: number; resold: number; grams_low: number; grams_high: number }[];
  activity: { when: string; kind: "purchase" | "build" | "listing"; text: string; mine: boolean }[];
  demo_data: boolean;
  methodology: { grams_per_part: { category: string; label: string; grams: number }[]; notes: string[] };
}

// ---- listing assistant ----
export interface ListingSuggestion {
  item_id: number; label: string; category: string; specs: Specs; condition: Condition; quantity_owned: number;
  can_list: boolean; problem: string | null; suggested_title: string; suggested_quantity: number;
  suggested_price_cents: number; price_low_cents: number; price_high_cents: number; price_basis: string;
}

// ---- global copilot ----
export interface CopilotChat {
  answer: string; source: "ai" | "safety_guard" | "fallback"; mode: "build" | "general";
  project_title: string | null; step_index: number | null; total_steps: number | null;
}

export interface TeardownComponent {
  category: string; label: string; marking: string | null; location_hint: string; confidence: number;
  worth_harvesting: boolean; extraction_tip: string; damage_flags: string[]; suggested_condition: Condition;
}
export interface TeardownAssessment {
  blocked: boolean; reasons: string[]; device_guess?: string; components: TeardownComponent[];
  warnings: string[]; safety_steps: string[]; saved_to_inventory: false; next?: string;
}
export interface TestProcedure { tool: string; steps: string[]; inputs: string[] }
export interface ComponentTestResult {
  verdict: "pass" | "fail" | "unsupported"; reason: string; changed?: boolean;
  item_id?: number; new_condition?: Condition;
}
export interface ResistorOption {
  kind: "single" | "series" | "parallel"; parts: number[]; result_ohm: number; error_pct: number; how: string;
}
export interface LedResistorResult {
  exact_ohm: number; chosen_ohm: number; actual_current_ma: number; resistor_power_mw: number; note: string;
}
export interface BuildPhotoCheck {
  safety_stop?: boolean; message?: string; available?: boolean; looks_consistent?: boolean;
  issues?: string[]; things_to_verify?: string[]; confidence?: number; disclaimer?: string;
}

// ---- cart and checkout ----
export interface CartLine { listing_id: number; quantity: number }
export interface PricedLine {
  listing_id: number; label: string; category: string; specs: Specs; condition: Condition; seller_name: string;
  unit_cents: number; quantity: number; quantity_available: number; line_cents: number; issue: string | null;
}
export interface CartPreview {
  lines: PricedLine[]; subtotal_cents: number; delivery_cents: number; total_cents: number;
  free_delivery_from_cents: number; ok: boolean;
}
export interface Address { full_name: string; phone: string; line1: string; city: string; pincode: string }
export type PayMethod = "upi" | "card" | "netbanking";
export interface PaymentLine { order_id: number; listing_id: number; label: string; quantity: number; unit_cents: number; line_cents: number; seller_name: string }
export interface Payment {
  id: number; reference: string; method: PayMethod; method_label: string; status: string;
  subtotal_cents: number; delivery_cents: number; total_cents: number; address: Address;
  lines: PaymentLine[]; created_at: string; note: string;
}

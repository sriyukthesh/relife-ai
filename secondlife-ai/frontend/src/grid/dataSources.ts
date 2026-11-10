/**
 * The ONLY file that talks to your API client. If your backend responses or function
 * names differ from the original ReLife API, adjust the mappers/calls here and the
 * grids keep working.
 */
import { api } from "../api";
import type { InventoryItem, Listing, Order } from "../types";
import type { Condition } from "./format";

export interface PartRow {
  id: number;
  label: string;
  category: string;
  specs: Record<string, string | number>;
  quantity: number;
  condition: Condition;
  source: string;
  ai_confidence: number | null;
  usable: boolean;
  missing_specs: string[];
}

export interface ListingRow {
  id: number;
  label: string;
  category: string;
  specs: Record<string, string | number>;
  seller_name: string;
  quantity: number;
  price_cents: number;
  condition: string;
  mine: boolean;
}

export interface OrderRow {
  id: number;
  label: string;
  quantity: number;
  total_cents: number;
  status: string;
  created_at: string;
}

const toPart = (x: InventoryItem): PartRow => ({
  id: x.id,
  label: x.label,
  category: x.category,
  specs: x.specs,
  quantity: x.quantity,
  condition: x.condition,
  source: x.source,
  ai_confidence: x.ai_confidence,
  usable: x.usable,
  missing_specs: x.missing_specs,
});

const toListing = (x: Listing): ListingRow => ({
  id: x.id,
  label: x.label,
  category: x.category,
  specs: x.specs,
  seller_name: x.seller_name,
  quantity: x.quantity,
  price_cents: x.price_cents,
  condition: x.condition,
  mine: x.mine,
});

const toOrder = (x: Order): OrderRow => ({
  id: x.id,
  label: x.label,
  quantity: x.quantity,
  total_cents: x.total_cents,
  status: x.status,
  created_at: x.created_at,
});

export const fetchParts = async (): Promise<PartRow[]> => (await api.inventory()).map(toPart);

export const updatePart = async (
  id: number,
  patch: { quantity?: number; condition?: Condition; label?: string },
): Promise<PartRow> => toPart(await api.patchItem(id, patch));

export const removePart = (id: number): Promise<void> => api.deleteItem(id);

/** Listings from other makers (not your own). */
export const fetchListings = async (): Promise<ListingRow[]> => (await api.listings(false)).map(toListing);

export const fetchOrders = async (): Promise<OrderRow[]> => (await api.orders()).map(toOrder);

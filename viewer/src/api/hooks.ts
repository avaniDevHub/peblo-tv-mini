// Viewer data hooks. The viewer reads ONLY the public catalogue endpoints —
// never /admin/* — so there is no auth token anywhere in this app.
import { useQuery } from "@tanstack/react-query";
import type { CatalogEnvelope, SearchResponse } from "../lib/types";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`) as Error & { status: number };
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export function useCatalog() {
  return useQuery({
    queryKey: ["catalog"],
    queryFn: () => getJson<CatalogEnvelope>("/catalog"),
    staleTime: 30_000,
  });
}

export function useSearch(params: { q?: string; category?: string; language?: string }) {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.category) sp.set("category", params.category);
  if (params.language) sp.set("language", params.language);
  const qs = sp.toString();
  const active = !!(params.q || params.category || params.language);
  return useQuery({
    queryKey: ["search", params],
    queryFn: () => getJson<SearchResponse>(`/catalog/search${qs ? `?${qs}` : ""}`),
    enabled: active,
  });
}

export { API_BASE };

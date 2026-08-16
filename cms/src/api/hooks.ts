// TanStack Query hooks. Chosen over hand-rolled fetch state because it gives us
// caching, request de-dup, and automatic refetch/invalidation for free — exactly
// what a CMS an editor hits 50x/week needs (fresh lists after every mutation).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import { useAuth } from "../lib/auth";
import type {
  Episode,
  PublishRun,
  Reference,
  Show,
  ValidationReport,
} from "../lib/types";

export function useReference() {
  return useQuery({
    queryKey: ["reference"],
    queryFn: () => apiFetch<Reference>("/reference"),
    staleTime: Infinity, // reference data doesn't change at runtime
  });
}

export function useShows(filters: { q?: string; section?: string; status?: string }) {
  const { token } = useAuth();
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.section) params.set("section", filters.section);
  if (filters.status) params.set("status_", filters.status);
  const qs = params.toString();
  return useQuery({
    queryKey: ["shows", filters, token],
    queryFn: () => apiFetch<Show[]>(`/admin/shows${qs ? `?${qs}` : ""}`, { token }),
  });
}

export function useShow(slug: string | undefined) {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["show", slug, token],
    queryFn: () => apiFetch<Show>(`/admin/shows/${slug}`, { token }),
    enabled: !!slug,
  });
}

export function useEpisodes(slug: string | undefined) {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["episodes", slug, token],
    queryFn: () => apiFetch<Episode[]>(`/admin/shows/${slug}/episodes`, { token }),
    enabled: !!slug,
  });
}

export function useValidationReport() {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["validation", token],
    queryFn: () => apiFetch<ValidationReport>("/admin/validation-report", { token }),
  });
}

export function usePublishRuns() {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["runs", token],
    queryFn: () => apiFetch<PublishRun[]>("/admin/publish-runs", { token }),
  });
}

// ---- mutations ----
export function useSaveShow() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { slug?: string; data: Partial<Show> }) =>
      vars.slug
        ? apiFetch<Show>(`/admin/shows/${vars.slug}`, { method: "PATCH", token, body: vars.data })
        : apiFetch<Show>("/admin/shows", { method: "POST", token, body: vars.data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shows"] });
      qc.invalidateQueries({ queryKey: ["validation"] });
    },
  });
}

export function useDeleteShow() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) =>
      apiFetch<void>(`/admin/shows/${slug}`, { method: "DELETE", token }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shows"] });
      qc.invalidateQueries({ queryKey: ["validation"] });
    },
  });
}

export function useSaveEpisode() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id?: number; slug: string; data: Partial<Episode> }) =>
      vars.id
        ? apiFetch<Episode>(`/admin/episodes/${vars.id}`, { method: "PATCH", token, body: vars.data })
        : apiFetch<Episode>(`/admin/shows/${vars.slug}/episodes`, {
            method: "POST",
            token,
            body: vars.data,
          }),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["episodes", vars.slug] });
      qc.invalidateQueries({ queryKey: ["validation"] });
    },
  });
}

export function useDeleteEpisode() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { episodeId: number; slug: string }) =>
      apiFetch<void>(`/admin/episodes/${vars.episodeId}`, { method: "DELETE", token }),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["episodes", vars.slug] });
      qc.invalidateQueries({ queryKey: ["validation"] });
    },
  });
}

export function useUploadArtwork() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { episodeId: number; kind: string; file: File; slug: string }) => {
      const fd = new FormData();
      fd.append("file", vars.file);
      return apiFetch<Episode>(`/admin/episodes/${vars.episodeId}/artwork/${vars.kind}`, {
        method: "POST",
        token,
        formData: fd,
      });
    },
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["episodes", vars.slug] });
      qc.invalidateQueries({ queryKey: ["validation"] });
    },
  });
}

export function usePublish() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<PublishRun>("/admin/catalog/publish", { method: "POST", token }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["validation"] });
    },
  });
}

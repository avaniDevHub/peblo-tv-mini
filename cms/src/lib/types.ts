// Shared types mirroring the API responses.
export type Role = "editor" | "admin";
export type Status = "draft" | "published";
export type ArtworkKind = "poster" | "banner" | "thumbnail";

export interface Show {
  id: number;
  slug: string;
  title: string;
  section: string | null;
  synopsis: string;
  categories: string[];
  status: Status;
}

export interface Artwork {
  id: number;
  kind: ArtworkKind;
  width: number;
  height: number;
  bytes: number;
  content_type: string;
  url: string;
}

export interface Episode {
  id: number;
  season_id: number;
  external_id: string | null;
  episode_number: number;
  title: string;
  synopsis: string;
  duration_seconds: number | null;
  language: string;
  content_group: string;
  status: Status;
  season_number: number;
  artwork: Artwork[];
}

export interface ValidationIssue {
  message: string;
  show_slug?: string | null;
  show_title?: string | null;
  episode_external_id?: string | null;
  episode_title?: string | null;
}

export interface ValidationGroup {
  code: string;
  title: string;
  fix_hint: string;
  issues: ValidationIssue[];
}

export interface ValidationReport {
  blocking: boolean;
  issue_count: number;
  groups: ValidationGroup[];
}

export interface PublishRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  published_by: string;
  outcome: "success" | "blocked" | "failed";
  catalog_key: string | null;
  show_count: number;
  entry_count: number;
  detail: Record<string, unknown>;
}

export interface ArtworkSpec {
  aspect: string;
  target_px: [number, number];
  max_kb: number;
}

export interface Reference {
  sections: string[];
  categories: string[];
  languages: string[];
  artwork_specs: Record<ArtworkKind, ArtworkSpec>;
}

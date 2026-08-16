// Types mirroring the published catalogue (GET /catalog) and search results.

export interface Hero {
  slug: string;
  title: string;
  synopsis: string;
  banner_url: string | null;
}

export interface ShowCard {
  slug: string;
  title: string;
  section: string;
  synopsis: string;
  categories: string[];
  languages: string[];
  poster_url: string | null;
  banner_url: string | null;
}

export interface SectionRow {
  key: string;
  shows: ShowCard[];
}

export interface EpisodeEntry {
  content_group: string;
  title: string;
  synopsis: string;
  episode_number: number;
  languages: string[];
  duration_seconds: Record<string, number | null>;
  thumbnail_url: string | null;
}

export interface SeasonBlock {
  season_number: number;
  episodes: EpisodeEntry[];
}

export interface ShowDetail extends ShowCard {
  seasons: SeasonBlock[];
  trailers: EpisodeEntry[];
}

export interface Catalog {
  hero: Hero | null;
  sections: SectionRow[];
  shows: Record<string, ShowDetail>;
  counts: { shows: number; entries: number };
}

export interface CatalogEnvelope {
  version: number;
  generated_at: string;
  catalog: Catalog;
}

export interface SearchResult {
  slug: string;
  title: string;
  section: string;
  synopsis: string;
  categories: string[];
  poster_url: string | null;
  banner_url: string | null;
  matched_on: string[];
}

export interface SearchResponse {
  query: Record<string, string | null>;
  count: number;
  results: SearchResult[];
}

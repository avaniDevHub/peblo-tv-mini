// Thin fetch wrapper that attaches the bearer token and normalises API errors
// into a typed ApiError carrying the editor-readable detail from the backend.

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  // The backend returns either a string detail or {errors:[...]}/{message,...}.
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

/** Turn an arbitrary error detail into readable lines for the editor. */
export function errorMessages(err: unknown): string[] {
  if (err instanceof ApiError) {
    const d = err.detail as any;
    if (typeof d === "string") return [d];
    if (d?.errors && Array.isArray(d.errors)) return d.errors;
    if (d?.message) return [d.message];
    if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x));
    return [err.message];
  }
  return [err instanceof Error ? err.message : String(err)];
}

interface RequestOpts {
  method?: string;
  token?: string;
  body?: unknown;
  formData?: FormData;
}

export async function apiFetch<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;
  let body: BodyInit | undefined;
  if (opts.formData) {
    body = opts.formData; // browser sets multipart boundary
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method || "GET",
    headers,
    body,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    const detail = data?.detail ?? data;
    throw new ApiError(res.status, detail, `HTTP ${res.status}`);
  }
  return data as T;
}

export { API_BASE };

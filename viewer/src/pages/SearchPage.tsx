import { useSearchParams } from "react-router-dom";
import { useSearch } from "../api/hooks";
import PosterCard from "../components/PosterCard";

// Reads query + filters from the URL so searches are shareable/bookmarkable.
export default function SearchPage({
  categories,
  languages,
}: {
  categories: string[];
  languages: string[];
}) {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const category = params.get("category") ?? "";
  const language = params.get("language") ?? "";

  const { data, isLoading, isError } = useSearch({ q, category, language });

  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  const hasCriteria = !!(q || category || language);

  return (
    <div>
      <div className="row" style={{ padding: "20px 32px 0", gap: 12, display: "flex", flexWrap: "wrap" }}>
        <input
          placeholder="Search shows, episodes, categories…"
          value={q}
          onChange={(e) => update("q", e.target.value)}
          style={{
            background: "rgba(255,255,255,0.08)",
            border: "1px solid rgba(255,255,255,0.15)",
            color: "#fff",
            padding: "8px 12px",
            borderRadius: 8,
            minWidth: 260,
            flex: 1,
          }}
        />
        <select value={category} onChange={(e) => update("category", e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select value={language} onChange={(e) => update("language", e.target.value)}>
          <option value="">All languages</option>
          {languages.map((l) => (
            <option key={l} value={l}>
              {l.toUpperCase()}
            </option>
          ))}
        </select>
      </div>

      {!hasCriteria ? (
        <div className="state">
          <h2>Search Peblo TV</h2>
          <p>Type a show or episode name, or pick a category or language above.</p>
        </div>
      ) : isLoading ? (
        <div className="state">Searching…</div>
      ) : isError ? (
        <div className="state">
          <h2>Search failed</h2>
          <p>Please try again.</p>
        </div>
      ) : (data?.count ?? 0) === 0 ? (
        <div className="state">
          <h2>No matches</h2>
          <p>
            Nothing found{q ? ` for “${q}”` : ""}
            {category ? ` in ${category}` : ""}
            {language ? ` (${language.toUpperCase()})` : ""}. Try a different search or clear the filters.
          </p>
        </div>
      ) : (
        <>
          <p className="matched" style={{ padding: "16px 32px 0" }}>
            {data!.count} result{data!.count === 1 ? "" : "s"}
          </p>
          <div className="search-grid">
            {data!.results.map((r) => (
              <PosterCard key={r.slug} show={r} matched={r.matched_on} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

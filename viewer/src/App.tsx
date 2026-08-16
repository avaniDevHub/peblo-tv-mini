import { useState } from "react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import { useCatalog } from "./api/hooks";
import HomePage from "./pages/HomePage";
import ShowDetailPage from "./pages/ShowDetailPage";
import SearchPage from "./pages/SearchPage";

// Language filter options come from the published catalogue's shows.
function langOptions(langs: Set<string>): string[] {
  return Array.from(langs).sort();
}

export default function App() {
  const catalog = useCatalog();
  const navigate = useNavigate();
  const [q, setQ] = useState("");

  // Collect languages + categories present in the catalogue for filter menus.
  const langs = new Set<string>();
  const cats = new Set<string>();
  if (catalog.data) {
    for (const s of catalog.data.catalog.sections) {
      for (const show of s.shows) {
        show.languages.forEach((l) => langs.add(l));
        show.categories.forEach((c) => cats.add(c));
      }
    }
  }

  function onSearchKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && q.trim()) {
      navigate(`/search?q=${encodeURIComponent(q.trim())}`);
    }
  }

  return (
    <>
      <nav className="nav">
        <Link to="/" className="logo">
          PEBLO<span>TV</span>
        </Link>
        <div className="spacer" />
        <input
          placeholder="Search shows, episodes, categories…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onSearchKey}
          aria-label="Search"
        />
        <button
          onClick={() => q.trim() && navigate(`/search?q=${encodeURIComponent(q.trim())}`)}
          style={{
            background: "transparent",
            border: "1px solid rgba(255,255,255,0.2)",
            color: "#fff",
            borderRadius: 8,
            padding: "8px 12px",
            cursor: "pointer",
          }}
        >
          Search
        </button>
      </nav>

      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route
          path="/search"
          element={<SearchPage categories={Array.from(cats).sort()} languages={langOptions(langs)} />}
        />
        <Route path="/show/:slug" element={<ShowDetailPage />} />
      </Routes>
    </>
  );
}

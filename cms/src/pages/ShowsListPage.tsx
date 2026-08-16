import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useReference, useShows } from "../api/hooks";
import { Empty, ErrorState, Loading } from "../components/states";

const PAGE_SIZE = 6;

export default function ShowsListPage() {
  const [q, setQ] = useState("");
  const [section, setSection] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);

  const ref = useReference();
  const shows = useShows({ q, section, status });

  // Reset to first page whenever a filter changes.
  const filtersKey = `${q}|${section}|${status}`;
  useMemo(() => setPage(0), [filtersKey]);

  const all = shows.data ?? [];
  const pageCount = Math.max(1, Math.ceil(all.length / PAGE_SIZE));
  const pageItems = all.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  return (
    <>
      <div className="panel">
        <div className="row">
          <h2 className="grow">Shows</h2>
          <Link to="/shows/new">
            <button>+ New show</button>
          </Link>
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <input
            className="grow"
            placeholder="Search show title…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <select value={section} onChange={(e) => setSection(e.target.value)} style={{ width: 160 }}>
            <option value="">All sections</option>
            {ref.data?.sections.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 140 }}>
            <option value="">All statuses</option>
            <option value="published">published</option>
            <option value="draft">draft</option>
          </select>
        </div>
      </div>

      <div className="panel">
        {shows.isLoading ? (
          <Loading label="Loading shows…" />
        ) : shows.isError ? (
          <ErrorState error={shows.error} retry={() => shows.refetch()} />
        ) : all.length === 0 ? (
          <Empty>
            No shows match your filters. <Link to="/shows/new">Create one?</Link>
          </Empty>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Section</th>
                  <th>Categories</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <Link to={`/shows/${s.slug}`}>{s.title}</Link>
                      <div className="small muted mono">{s.slug}</div>
                    </td>
                    <td>{s.section || <span className="muted">— none —</span>}</td>
                    <td className="small">{s.categories.join(", ") || <span className="muted">—</span>}</td>
                    <td>
                      <span className={`badge ${s.status}`}>{s.status}</span>
                    </td>
                    <td>
                      <Link to={`/shows/${s.slug}`}>Edit</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="row" style={{ marginTop: 12, justifyContent: "space-between" }}>
              <span className="small muted">
                {all.length} show{all.length === 1 ? "" : "s"} · page {page + 1} of {pageCount}
              </span>
              <div className="row">
                <button className="ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                  ← Prev
                </button>
                <button
                  className="ghost"
                  disabled={page >= pageCount - 1}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next →
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}

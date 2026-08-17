import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useEpisodes, useReference, useSaveShow, useShow, useDeleteShow } from "../api/hooks";
import { ErrorLines, ErrorState, Loading } from "../components/states";
import EpisodeEditor from "../components/EpisodeEditor";
import type { Episode } from "../lib/types";

const EPISODE_PAGE_SIZE = 10;

export default function ShowEditPage({ mode }: { mode: "new" | "edit" }) {
  const { slug } = useParams();
  const navigate = useNavigate();
  const ref = useReference();
  const isNew = mode === "new";

  const show = useShow(isNew ? undefined : slug);
  const episodes = useEpisodes(isNew ? undefined : slug);
  const saveShow = useSaveShow();
  const deleteShow = useDeleteShow();

  const [editingEpisode, setEditingEpisode] = useState<Episode | "new" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Episode list filters
  const [episodeSearch, setEpisodeSearch] = useState("");
  const [episodeLanguage, setEpisodeLanguage] = useState("");
  const [episodeStatus, setEpisodeStatus] = useState("");
  const [episodePage, setEpisodePage] = useState(0);

  // Reset to first page whenever episode filters change.
  const episodeFiltersKey = `${episodeSearch}|${episodeLanguage}|${episodeStatus}`;
  useMemo(() => setEpisodePage(0), [episodeFiltersKey]);

  // local form seeded from server data
  const [form, setForm] = useState({
    slug: "",
    title: "",
    section: "",
    synopsis: "",
    categories: [] as string[],
    status: "draft" as "draft" | "published",
  });
  const [initialised, setInitialised] = useState(false);
  if (!isNew && show.data && !initialised) {
    setForm({
      slug: show.data.slug,
      title: show.data.title,
      section: show.data.section ?? "",
      synopsis: show.data.synopsis,
      categories: show.data.categories,
      status: show.data.status,
    });
    setInitialised(true);
  }

  const set = (k: keyof typeof form, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  async function submitShow() {
    const data = { ...form, section: form.section || null };
    try {
      if (isNew) {
        await saveShow.mutateAsync({ data });
        navigate(`/shows/${form.slug}`);
      } else {
        const { slug: _slug, ...patch } = data; // slug is immutable
        await saveShow.mutateAsync({ slug, data: patch });
      }
    } catch {
      /* shown below */
    }
  }

  async function handleDelete() {
    if (!slug) return;
    try {
      await deleteShow.mutateAsync(slug);
      navigate("/shows");
    } catch {
      /* error shown below */
    }
  }

  if (!isNew && show.isLoading) return <Loading label="Loading show…" />;
  if (!isNew && show.isError) return <ErrorState error={show.error} retry={() => show.refetch()} />;

  return (
    <>
      <div className="panel">
        <div className="row">
          <h2 className="grow">{isNew ? "New show" : form.title || "Edit show"}</h2>
          {!isNew && <span className={`badge ${form.status}`}>{form.status}</span>}
        </div>

        {saveShow.isError && <ErrorLines error={saveShow.error} />}
        {deleteShow.isError && <ErrorLines error={deleteShow.error} />}
        {saveShow.isSuccess && !isNew && <div className="okbox small">✓ Saved</div>}

        <div className="row">
          <div className="grow">
            <label>Slug {isNew ? "" : "(immutable)"}</label>
            <input
              className="mono"
              value={form.slug}
              disabled={!isNew}
              placeholder="motis-many-lives"
              onChange={(e) => set("slug", e.target.value)}
            />
          </div>
          <div className="grow">
            <label>Title</label>
            <input value={form.title} onChange={(e) => set("title", e.target.value)} />
          </div>
        </div>

        <div className="row">
          <div style={{ width: 200 }}>
            <label>Section</label>
            <select value={form.section} onChange={(e) => set("section", e.target.value)}>
              <option value="">— none —</option>
              {ref.data?.sections.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <div className="small muted">Required before publishing.</div>
          </div>
          <div style={{ width: 200 }}>
            <label>Status</label>
            <select
              value={form.status}
              onChange={(e) => set("status", e.target.value as "draft" | "published")}
            >
              <option value="draft">draft</option>
              <option value="published">published</option>
            </select>
          </div>
          <div className="grow">
            <label>Categories</label>
            <div className="row" style={{ gap: 6 }}>
              {ref.data?.categories.map((c) => {
                const on = form.categories.includes(c);
                return (
                  <span
                    key={c}
                    className={`pill ${on ? "active" : ""}`}
                    onClick={() =>
                      set(
                        "categories",
                        on ? form.categories.filter((x) => x !== c) : [...form.categories, c]
                      )
                    }
                  >
                    {c}
                  </span>
                );
              })}
            </div>
          </div>
        </div>

        <label>Synopsis</label>
        <textarea value={form.synopsis} onChange={(e) => set("synopsis", e.target.value)} />

        <div className="row" style={{ marginTop: 10 }}>
          <button onClick={submitShow} disabled={saveShow.isPending}>
            {saveShow.isPending ? "Saving…" : isNew ? "Create show" : "Save show"}
          </button>
          <button className="ghost" onClick={() => navigate("/shows")}>
            Back to list
          </button>
          {!isNew && (
            <>
              {!confirmDelete ? (
                <button className="ghost" onClick={() => setConfirmDelete(true)} style={{ marginLeft: 10 }}>
                  Delete show
                </button>
              ) : (
                <>
                  <span style={{ marginLeft: 10, color: "#d9534f", fontWeight: "bold" }}>Delete this show?</span>
                  <button
                    onClick={handleDelete}
                    disabled={deleteShow.isPending}
                    style={{ marginLeft: 10, background: "#d9534f" }}
                  >
                    {deleteShow.isPending ? "Deleting…" : "Confirm delete"}
                  </button>
                  <button className="ghost" onClick={() => setConfirmDelete(false)} style={{ marginLeft: 5 }}>
                    Cancel
                  </button>
                </>
              )}
            </>
          )}
        </div>
      </div>

      {!isNew && (
        <div className="panel">
          <div className="row">
            <h2 className="grow">Episodes</h2>
            <button onClick={() => setEditingEpisode("new")}>+ New episode</button>
          </div>

          {episodes.isLoading ? (
            <Loading label="Loading episodes…" />
          ) : episodes.isError ? (
            <ErrorState error={episodes.error} retry={() => episodes.refetch()} />
          ) : (episodes.data?.length ?? 0) === 0 ? (
            <div className="state">No episodes yet. Add the first one.</div>
          ) : (
            <>
              <div className="row" style={{ marginBottom: 12 }}>
                <input
                  className="grow"
                  placeholder="Search episode title…"
                  value={episodeSearch}
                  onChange={(e) => setEpisodeSearch(e.target.value)}
                />
                <select
                  value={episodeLanguage}
                  onChange={(e) => setEpisodeLanguage(e.target.value)}
                  style={{ width: 120 }}
                >
                  <option value="">All languages</option>
                  {Array.from(new Set(episodes.data!.map((ep) => ep.language)))
                    .sort()
                    .map((lang) => (
                      <option key={lang} value={lang}>
                        {lang}
                      </option>
                    ))}
                </select>
                <select
                  value={episodeStatus}
                  onChange={(e) => setEpisodeStatus(e.target.value)}
                  style={{ width: 120 }}
                >
                  <option value="">All statuses</option>
                  <option value="published">published</option>
                  <option value="draft">draft</option>
                </select>
              </div>

              {(() => {
                // Filter episodes
                const filtered = episodes.data!.filter((ep) => {
                  const matchesSearch =
                    episodeSearch === "" || ep.title.toLowerCase().includes(episodeSearch.toLowerCase());
                  const matchesLanguage = episodeLanguage === "" || ep.language === episodeLanguage;
                  const matchesStatus = episodeStatus === "" || ep.status === episodeStatus;
                  return matchesSearch && matchesLanguage && matchesStatus;
                });

                const pageCount = Math.max(1, Math.ceil(filtered.length / EPISODE_PAGE_SIZE));
                const pageItems = filtered.slice(
                  episodePage * EPISODE_PAGE_SIZE,
                  episodePage * EPISODE_PAGE_SIZE + EPISODE_PAGE_SIZE
                );

                return (
                  <>
                    <table>
                      <thead>
                        <tr>
                          <th>S/E</th>
                          <th>Title</th>
                          <th>Lang</th>
                          <th>Duration</th>
                          <th>Artwork</th>
                          <th>Status</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {pageItems.length === 0 ? (
                          <tr>
                            <td colSpan={7} style={{ textAlign: "center", padding: 20 }}>
                              <span className="muted">No episodes match your filters.</span>
                            </td>
                          </tr>
                        ) : (
                          pageItems.map((ep) => (
                            <tr key={ep.id}>
                              <td className="mono">
                                S{ep.season_number}E{ep.episode_number}
                                {ep.season_number === 0 && <span className="small muted"> (trailer)</span>}
                              </td>
                              <td>{ep.title}</td>
                              <td>
                                <span className="badge lang">{ep.language}</span>
                              </td>
                              <td>{ep.duration_seconds ? `${ep.duration_seconds}s` : <span className="muted">—</span>}</td>
                              <td className="small">
                                {["poster", "banner", "thumbnail"].map((k) => {
                                  const has = ep.artwork.some((a) => a.kind === k);
                                  return (
                                    <span key={k} title={k} style={{ opacity: has ? 1 : 0.3 }}>
                                      {k[0].toUpperCase()}
                                    </span>
                                  );
                                })}
                              </td>
                              <td>
                                <span className={`badge ${ep.status}`}>{ep.status}</span>
                              </td>
                              <td>
                                <button
                                  className="ghost small"
                                  onClick={() => setEditingEpisode(ep)}
                                >
                                  Edit
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                    {filtered.length > 0 && (
                      <div className="row" style={{ marginTop: 12, justifyContent: "space-between" }}>
                        <span className="small muted">
                          {filtered.length} episode{filtered.length === 1 ? "" : "s"} · page {episodePage + 1} of{" "}
                          {pageCount}
                        </span>
                        <div className="row">
                          <button
                            className="ghost"
                            disabled={episodePage === 0}
                            onClick={() => setEpisodePage((p) => p - 1)}
                          >
                            ← Prev
                          </button>
                          <button
                            className="ghost"
                            disabled={episodePage >= pageCount - 1}
                            onClick={() => setEpisodePage((p) => p + 1)}
                          >
                            Next →
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                );
              })()}
            </>
          )}
        </div>
      )}

      {editingEpisode && slug && (
        <EpisodeEditor
          slug={slug}
          episode={editingEpisode === "new" ? undefined : editingEpisode}
          onDone={() => setEditingEpisode(null)}
          onCancel={() => setEditingEpisode(null)}
        />
      )}
    </>
  );
}

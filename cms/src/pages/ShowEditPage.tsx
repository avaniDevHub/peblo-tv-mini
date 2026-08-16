import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useEpisodes, useReference, useSaveShow, useShow, useDeleteShow } from "../api/hooks";
import { ErrorLines, ErrorState, Loading } from "../components/states";
import EpisodeEditor from "../components/EpisodeEditor";
import type { Episode } from "../lib/types";

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
                {episodes.data!.map((ep) => (
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
                      <button className="ghost small" onClick={() => setEditingEpisode(ep)}>
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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

// Create/edit a single episode, including the three artwork slots. Shown inline
// under a show. Publishing an episode is blocked server-side until it has a
// duration + all required artwork; we surface those errors verbatim.
import { useState } from "react";
import { useReference, useSaveEpisode, useDeleteEpisode } from "../api/hooks";
import { ErrorLines } from "./states";
import ArtworkSlot from "./ArtworkSlot";
import type { ArtworkKind, Episode } from "../lib/types";

const KINDS: ArtworkKind[] = ["poster", "banner", "thumbnail"];

interface Props {
  slug: string;
  episode?: Episode;
  onDone: () => void;
  onCancel: () => void;
}

export default function EpisodeEditor({ slug, episode, onDone, onCancel }: Props) {
  const ref = useReference();
  const save = useSaveEpisode();
  const deleteEp = useDeleteEpisode();
  const isEdit = !!episode;
  const [confirmDelete, setConfirmDelete] = useState(false);

  const [form, setForm] = useState({
    season_number: episode?.season_number ?? 1,
    episode_number: episode?.episode_number ?? 1,
    title: episode?.title ?? "",
    synopsis: episode?.synopsis ?? "",
    duration_seconds: episode?.duration_seconds ?? ("" as number | ""),
    language: episode?.language ?? "en",
    content_group: episode?.content_group ?? "",
    status: episode?.status ?? "draft",
  });

  const set = (k: keyof typeof form, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  async function submit() {
    const contentGroup = form.content_group.trim();
    const fallbackContentGroup = `${slug}-s${String(form.season_number).padStart(2, "0")}e${String(form.episode_number).padStart(2, "0")}`;
    const data: Record<string, unknown> = {
      ...form,
      content_group: contentGroup || fallbackContentGroup,
      duration_seconds: form.duration_seconds === "" ? null : Number(form.duration_seconds),
    };
    if (isEdit) {
      // Only send editable fields on PATCH (season is fixed once created here).
      delete data.season_number;
    }
    try {
      await save.mutateAsync({ id: episode?.id, slug, data });
      onDone();
    } catch {
      /* error shown below via save.error */
    }
  }

  async function handleDelete() {
    if (!episode) return;
    try {
      await deleteEp.mutateAsync({ episodeId: episode.id, slug });
      onDone();
    } catch {
      /* error shown below via deleteEp.error */
    }
  }

  return (
    <div className="panel" style={{ background: "#fbfcfe" }}>
      <div className="row">
        <h2 className="grow">{isEdit ? `Edit episode: ${episode!.title}` : "New episode"}</h2>
        <button className="ghost" onClick={onCancel}>
          Close
        </button>
      </div>

      {save.isError && <ErrorLines error={save.error} />}
      {deleteEp.isError && <ErrorLines error={deleteEp.error} />}

      <div className="row">
        <div style={{ width: 110 }}>
          <label>Season</label>
          <input
            type="number"
            value={form.season_number}
            disabled={isEdit}
            onChange={(e) => set("season_number", Number(e.target.value))}
          />
          <div className="small muted">0 = trailer</div>
        </div>
        <div style={{ width: 110 }}>
          <label>Episode #</label>
          <input
            type="number"
            value={form.episode_number}
            onChange={(e) => set("episode_number", Number(e.target.value))}
          />
        </div>
        <div className="grow">
          <label>Title</label>
          <input value={form.title} onChange={(e) => set("title", e.target.value)} />
        </div>
      </div>

      <div className="row">
        <div style={{ width: 140 }}>
          <label>Duration (sec)</label>
          <input
            type="number"
            value={form.duration_seconds}
            onChange={(e) => set("duration_seconds", e.target.value === "" ? "" : Number(e.target.value))}
          />
        </div>
        <div style={{ width: 140 }}>
          <label>Language</label>
          <select value={form.language} onChange={(e) => set("language", e.target.value)}>
            {ref.data?.languages.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div className="grow">
          <label>Content group</label>
          <input
            className="mono"
            placeholder="e.g. motis-many-lives-s01e01"
            value={form.content_group}
            onChange={(e) => set("content_group", e.target.value)}
          />
          <div className="small muted">Episodes sharing this are language variants of the same episode.</div>
        </div>
        <div style={{ width: 140 }}>
          <label>Status</label>
          <select value={form.status} onChange={(e) => set("status", e.target.value)}>
            <option value="draft">draft</option>
            <option value="published">published</option>
          </select>
        </div>
      </div>

      <label>Synopsis</label>
      <textarea value={form.synopsis} onChange={(e) => set("synopsis", e.target.value)} />

      <div className="row" style={{ marginTop: 10 }}>
        <button onClick={submit} disabled={save.isPending}>
          {save.isPending ? "Saving…" : isEdit ? "Save changes" : "Create episode"}
        </button>
        {isEdit && (
          <>
            {!confirmDelete ? (
              <button className="ghost" onClick={() => setConfirmDelete(true)} style={{ marginLeft: 10 }}>
                Delete episode
              </button>
            ) : (
              <>
                <span style={{ marginLeft: 10, color: "#d9534f", fontWeight: "bold" }}>Delete this episode?</span>
                <button
                  onClick={handleDelete}
                  disabled={deleteEp.isPending}
                  style={{ marginLeft: 10, background: "#d9534f" }}
                >
                  {deleteEp.isPending ? "Deleting…" : "Confirm delete"}
                </button>
                <button className="ghost" onClick={() => setConfirmDelete(false)} style={{ marginLeft: 5 }}>
                  Cancel
                </button>
              </>
            )}
          </>
        )}
      </div>

      {isEdit && ref.data && (
        <>
          <h2 style={{ marginTop: 20 }}>Artwork</h2>
          <p className="small muted">
            An episode can’t be published without a poster, banner and thumbnail (trailers only need a
            thumbnail).
          </p>
          <div className="slots">
            {KINDS.map((kind) => (
              <ArtworkSlot
                key={kind}
                kind={kind}
                spec={ref.data!.artwork_specs[kind]}
                episodeId={episode!.id}
                slug={slug}
                existing={episode!.artwork.find((a) => a.kind === kind)}
              />
            ))}
          </div>
        </>
      )}
      {!isEdit && (
        <p className="small muted" style={{ marginTop: 12 }}>
          Save the episode first, then upload artwork.
        </p>
      )}
    </div>
  );
}

// One labelled artwork upload slot: shows required dimensions, a live preview,
// and human-readable errors from the server. Client-side check is a courtesy;
// the server is the source of truth (the challenge explicitly warns against
// client-side-only validation), so we always POST and show the server verdict.
import { useState } from "react";
import { useUploadArtwork } from "../api/hooks";
import { errorMessages } from "../api/client";
import type { ArtworkKind, ArtworkSpec, Artwork } from "../lib/types";

interface Props {
  kind: ArtworkKind;
  spec: ArtworkSpec;
  episodeId: number;
  slug: string;
  existing?: Artwork;
}

export default function ArtworkSlot({ kind, spec, episodeId, slug, existing }: Props) {
  const upload = useUploadArtwork();
  const [preview, setPreview] = useState<string | null>(existing?.url ?? null);
  const [localErrors, setLocalErrors] = useState<string[]>([]);
  const [ok, setOk] = useState(false);

  const [tw, th] = spec.target_px;

  async function onFile(file: File) {
    setOk(false);
    setLocalErrors([]);
    // Optimistic local preview so the editor sees the image instantly.
    setPreview(URL.createObjectURL(file));
    try {
      await upload.mutateAsync({ episodeId, kind, file, slug });
      setOk(true);
    } catch (e) {
      // Revert preview to whatever the server had; surface readable errors.
      setPreview(existing?.url ?? null);
      setLocalErrors(errorMessages(e));
    }
  }

  return (
    <div className={`slot ${kind}`}>
      <h4>{kind[0].toUpperCase() + kind.slice(1)}</h4>
      <div className="spec">
        {spec.aspect} · ~{tw}×{th}px · ≤{spec.max_kb} KB
      </div>
      <div className="preview">
        {preview ? (
          <img src={preview} alt={`${kind} preview`} />
        ) : (
          <span className="empty">No image yet</span>
        )}
      </div>
      <input
        type="file"
        accept="image/*"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
        disabled={upload.isPending}
      />
      {upload.isPending && <div className="small muted">Uploading…</div>}
      {ok && <div className="okbox small">✓ Saved</div>}
      {localErrors.length > 0 && (
        <div className="errorbox small">
          {localErrors.map((m, i) => (
            <div key={i}>• {m}</div>
          ))}
        </div>
      )}
      {existing && !localErrors.length && (
        <div className="small muted">
          Current: {existing.width}×{existing.height}, {Math.round(existing.bytes / 1024)} KB
        </div>
      )}
    </div>
  );
}

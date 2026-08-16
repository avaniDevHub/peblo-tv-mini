import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useCatalog } from "../api/hooks";
import Img from "../components/Img";
import type { EpisodeEntry } from "../lib/types";

function fmtDuration(entry: EpisodeEntry): string {
  // Show the first available language's duration (they're usually close).
  const first = entry.languages[0];
  const secs = entry.duration_seconds[first];
  if (!secs) return "";
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

export default function ShowDetailPage() {
  const { slug } = useParams();
  const { data, isLoading, isError, error } = useCatalog();
  const [activeSeason, setActiveSeason] = useState<number | null>(null);

  if (isLoading) return <div className="state">Loading…</div>;
  if (isError) {
    const status = (error as Error & { status?: number }).status;
    return (
      <div className="state">
        <h2>{status === 404 ? "Catalogue not published yet" : "Couldn’t load this show"}</h2>
        <Link to="/" className="cta" style={{ marginTop: 16 }}>
          ← Home
        </Link>
      </div>
    );
  }

  const show = slug ? data!.catalog.shows[slug] : undefined;
  if (!show) {
    return (
      <div className="state">
        <h2>Show not found</h2>
        <p>It may have been unpublished.</p>
        <Link to="/" className="cta">
          ← Home
        </Link>
      </div>
    );
  }

  // Season 0 (trailers) is intentionally NOT among `seasons`; it's `trailers`.
  const seasons = show.seasons;
  const currentSeason =
    activeSeason ?? (seasons.length > 0 ? seasons[0].season_number : null);
  const seasonBlock = seasons.find((s) => s.season_number === currentSeason);

  return (
    <>
      <section className="detail-hero">
        <div
          className="bg"
          style={
            show.banner_url ? { backgroundImage: `url(${show.banner_url})` } : { background: "#1c212b" }
          }
        />
        <div className="scrim" />
        <div className="content">
          <Link to="/" className="back">
            ← Back to browse
          </Link>
          <h1>{show.title}</h1>
          <div className="chips">
            <span className="chip">{show.section}</span>
            {show.categories.map((c) => (
              <span className="chip" key={c}>
                {c}
              </span>
            ))}
            {show.languages.map((l) => (
              <span className="chip lang" key={l}>
                {l.toUpperCase()}
              </span>
            ))}
          </div>
          <p style={{ maxWidth: 640, color: "#e8eaee" }}>{show.synopsis}</p>
        </div>
      </section>

      <div className="detail-body">
        {seasons.length > 1 && (
          <div className="season-tabs">
            {seasons.map((s) => (
              <button
                key={s.season_number}
                className={s.season_number === currentSeason ? "active" : ""}
                onClick={() => setActiveSeason(s.season_number)}
              >
                Season {s.season_number}
              </button>
            ))}
          </div>
        )}

        {seasonBlock ? (
          <div>
            {seasonBlock.episodes.map((ep) => (
              <div className="ep" key={ep.content_group}>
                <div className="epnum">{ep.episode_number}</div>
                <Img src={ep.thumbnail_url} alt={ep.title} className="thumb thumb-16x9" />
                <div className="meta">
                  <h4>{ep.title}</h4>
                  <p>{ep.synopsis}</p>
                  <div className="chips" style={{ marginTop: 6 }}>
                    {/* Language options for this grouped episode */}
                    {ep.languages.map((l) => (
                      <span className="chip lang" key={l}>
                        {l.toUpperCase()}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="dur">{fmtDuration(ep)}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="state">No episodes in this show yet.</div>
        )}

        {/* Trailers (Season 0) surfaced separately — never as a normal season. */}
        {show.trailers.length > 0 && (
          <>
            <h2 style={{ marginTop: 36 }}>Trailers</h2>
            <div>
              {show.trailers.map((t) => (
                <div className="ep" key={t.content_group}>
                  <div className="epnum">▶</div>
                  <Img src={t.thumbnail_url} alt={t.title} className="thumb thumb-16x9" />
                  <div className="meta">
                    <h4>{t.title}</h4>
                    <p>{t.synopsis}</p>
                  </div>
                  <div className="dur">{fmtDuration(t)}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
}

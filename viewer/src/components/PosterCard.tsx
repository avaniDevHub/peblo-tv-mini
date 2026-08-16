import { Link } from "react-router-dom";
import Img from "./Img";
import type { ShowCard, SearchResult } from "../lib/types";

// A poster card used in home rows and search results. Uses the POSTER artwork
// (2:3) — the right surface for browse rows.
export default function PosterCard({
  show,
  matched,
}: {
  show: ShowCard | SearchResult;
  matched?: string[];
}) {
  return (
    <Link to={`/show/${show.slug}`} className="card">
      <Img src={show.poster_url} alt={show.title} className="poster" />
      <div className="title">{show.title}</div>
      {matched && matched.length > 0 && <div className="matched">matched: {matched.join(", ")}</div>}
    </Link>
  );
}

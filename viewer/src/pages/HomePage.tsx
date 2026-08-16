import { Link } from "react-router-dom";
import { useCatalog } from "../api/hooks";
import PosterCard from "../components/PosterCard";

export default function HomePage() {
  const { data, isLoading, isError, error, refetch } = useCatalog();

  if (isLoading) return <div className="state">Loading Peblo TV…</div>;

  // No catalogue published yet -> friendly empty state (404 from API).
  if (isError) {
    const status = (error as Error & { status?: number }).status;
    if (status === 404) {
      return (
        <div className="state">
          <h2>Nothing to watch yet 🎬</h2>
          <p>The catalogue hasn’t been published. Check back soon!</p>
        </div>
      );
    }
    return (
      <div className="state">
        <h2>Couldn’t load Peblo TV</h2>
        <p>Please try again.</p>
        <button onClick={() => refetch()} style={{ padding: "8px 16px", cursor: "pointer" }}>
          Retry
        </button>
      </div>
    );
  }

  const cat = data!.catalog;
  const hero = cat.hero;

  if (cat.sections.length === 0) {
    return (
      <div className="state">
        <h2>Nothing to watch yet 🎬</h2>
        <p>The catalogue is empty. Check back soon!</p>
      </div>
    );
  }

  return (
    <>
      {hero && (
        <section className="hero">
          <div
            className="bg"
            style={hero.banner_url ? { backgroundImage: `url(${hero.banner_url})` } : { background: "#1c212b" }}
          />
          <div className="scrim" />
          <div className="content">
            <h1>{hero.title}</h1>
            <p>{hero.synopsis}</p>
            <Link to={`/show/${hero.slug}`} className="cta">
              ▶ Watch
            </Link>
          </div>
        </section>
      )}

      <div className="rows">
        {cat.sections.map((section) => (
          <section className="row" key={section.key}>
            <h2>{section.key}</h2>
            <div className="rail">
              {section.shows.map((show) => (
                <PosterCard key={show.slug} show={show} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}

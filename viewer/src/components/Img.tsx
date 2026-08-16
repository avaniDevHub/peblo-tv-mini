// Progressive image: shows a shimmering skeleton until the image loads, then
// fades it in. Handles slow networks gracefully, and shows a text fallback if
// the image is missing or errors. Uses native lazy-loading + async decoding.
import { useState } from "react";

export default function Img({
  src,
  alt,
  className,
}: {
  src: string | null;
  alt: string;
  className?: string;
}) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div className={className}>
        <div className="img-fallback">{alt}</div>
      </div>
    );
  }
  return (
    <div className={className}>
      <div className={`skeleton ${loaded ? "hidden" : ""}`} />
      <img
        className={`img ${loaded ? "loaded" : ""}`}
        src={src}
        alt={alt}
        loading="lazy"
        decoding="async"
        onLoad={() => setLoaded(true)}
        onError={() => setFailed(true)}
      />
    </div>
  );
}

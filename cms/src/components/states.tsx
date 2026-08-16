// Reusable loading / empty / error / permission-denied states so every page
// handles them consistently (Part B requirement #4).
import { ReactNode } from "react";
import { ApiError, errorMessages } from "../api/client";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <div className="state">⏳ {label}</div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>;
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  // Permission errors get a dedicated, friendly message.
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return (
      <div className="state error">
        <p>🔒 You don’t have permission to view this.</p>
        <p className="small muted">
          {error.status === 403
            ? "This action needs a different role. Switch role in the top-right if you have access."
            : "Your session isn’t authorised. Pick a role in the top-right."}
        </p>
      </div>
    );
  }
  return (
    <div className="state error">
      <p>⚠️ Something went wrong.</p>
      {errorMessages(error).map((m, i) => (
        <p key={i} className="small">
          {m}
        </p>
      ))}
      {retry && (
        <button className="secondary" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function ErrorLines({ error }: { error: unknown }) {
  return (
    <div className="errorbox">
      {errorMessages(error).map((m, i) => (
        <div key={i}>• {m}</div>
      ))}
    </div>
  );
}

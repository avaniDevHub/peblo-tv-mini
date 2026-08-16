import { useAuth } from "../lib/auth";
import { usePublish, usePublishRuns, useValidationReport } from "../api/hooks";
import { ErrorLines, ErrorState, Loading } from "../components/states";

function fmtTime(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function PublishPage() {
  const { role } = useAuth();
  const report = useValidationReport();
  const runs = usePublishRuns();
  const publish = usePublish();

  const isAdmin = role === "admin";
  const blocking = report.data?.blocking ?? true;
  const canPublish = isAdmin && !blocking && !publish.isPending;

  // Compose a precise reason for the disabled button.
  let disabledReason = "";
  if (!isAdmin) disabledReason = "Only an admin can publish. Switch role in the top-right.";
  else if (report.isLoading) disabledReason = "Checking validation…";
  else if (blocking)
    disabledReason = `Fix ${report.data?.issue_count ?? ""} blocking issue(s) below first.`;

  return (
    <>
      <div className="panel">
        <div className="row">
          <h2 className="grow">Publish catalogue</h2>
          <div style={{ textAlign: "right" }}>
            <button disabled={!canPublish} onClick={() => publish.mutate()}>
              {publish.isPending ? "Publishing…" : "🚀 Publish now"}
            </button>
            {!canPublish && disabledReason && (
              <div className="small muted" style={{ marginTop: 4 }}>
                {disabledReason}
              </div>
            )}
          </div>
        </div>

        {publish.isSuccess && (
          <div className="okbox">
            ✓ Published run #{publish.data.id}: {publish.data.show_count} shows,{" "}
            {publish.data.entry_count} entries. The viewer will pick it up on next load.
          </div>
        )}
        {publish.isError && <ErrorLines error={publish.error} />}
      </div>

      <div className="panel">
        <h2>Validation report</h2>
        <p className="small muted">Everything currently blocking a clean publish, grouped so you can fix it.</p>
        {report.isLoading ? (
          <Loading label="Running validation…" />
        ) : report.isError ? (
          <ErrorState error={report.error} retry={() => report.refetch()} />
        ) : report.data!.issue_count === 0 ? (
          <div className="okbox">✓ No blocking issues. You’re clear to publish.</div>
        ) : (
          report.data!.groups.map((g) => (
            <div key={g.code} className="warnbox">
              <strong>
                {g.title} ({g.issues.length})
              </strong>
              <div className="small muted" style={{ margin: "2px 0 8px" }}>
                How to fix: {g.fix_hint}
              </div>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {g.issues.map((iss, i) => (
                  <li key={i} className="small">
                    {iss.message}
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </div>

      <div className="panel">
        <h2>Run history</h2>
        {runs.isLoading ? (
          <Loading label="Loading runs…" />
        ) : runs.isError ? (
          <ErrorState error={runs.error} retry={() => runs.refetch()} />
        ) : (runs.data?.length ?? 0) === 0 ? (
          <div className="state">No publish runs yet.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>When</th>
                <th>By</th>
                <th>Outcome</th>
                <th>Shows</th>
                <th>Entries</th>
                <th>Snapshot</th>
              </tr>
            </thead>
            <tbody>
              {runs.data!.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td className="small">{fmtTime(r.started_at)}</td>
                  <td>{r.published_by}</td>
                  <td>
                    <span
                      className="badge"
                      style={{
                        background:
                          r.outcome === "success"
                            ? "var(--ok-bg)"
                            : r.outcome === "blocked"
                            ? "var(--warn-bg)"
                            : "var(--danger-bg)",
                        color:
                          r.outcome === "success"
                            ? "var(--ok)"
                            : r.outcome === "failed"
                            ? "var(--danger)"
                            : "#8a6d00",
                      }}
                    >
                      {r.outcome}
                    </span>
                  </td>
                  <td>{r.show_count}</td>
                  <td>{r.entry_count}</td>
                  <td className="small mono">{r.catalog_key ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

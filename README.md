# Peblo TV Mini

CMS upload → published catalogue → Netflix-style browse.

```
CMS (React)  ──►  API (FastAPI + Postgres)  ──►  publish job  ──►  catalogue.json in storage
                                                                          │
                                          Viewer UI (React)  ◄────────────┘
```

Three apps + the pipeline that runs them:

| Layer | Stack | Port | What it is |
|---|---|---|---|
| **API** | FastAPI + SQLAlchemy + Alembic + Postgres | `8000` | CRUD, artwork upload/validation, publish job, public catalogue + search |
| **CMS** | React + TS + Vite + TanStack Query | `5173` | Internal editor tool: shows/episodes, artwork slots, publish page |
| **Viewer** | React + TS + Vite + TanStack Query | `5174` | Public browse UI — reads **only** the published catalogue |

---

## Run it

### Docker (everything, seeded and published)

```bash
docker compose up --build
```

Then open:

- **Viewer** → http://localhost:5174
- **CMS** → http://localhost:5173
- **API docs** → http://localhost:8000/docs · **health** → http://localhost:8000/health

No `.env` needed — compose has working defaults for every variable (`.env.example` documents them all). On first boot the API: runs migrations → seeds the (deliberately imperfect) data → **prints the validation report showing the built-in block** → applies the one documented fix → publishes, so the viewer is populated. To see the genuine empty-state / validation-gate instead, set `PEBLO_DEMO_PUBLISH=0` (see [First-boot behaviour](#first-boot-behaviour-important)).

**Sign-in (CMS):** a role switcher in the top bar toggles `admin` (can publish/CRUD) vs `editor` (cannot publish/only CRUD). Demo bearer tokens map to roles server-side.

### Local dev (no Docker)

```bash
# API — needs a Postgres, or point DATABASE_URL at sqlite for a quick spin
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="sqlite:///./dev.db"      # or a real postgres URL
alembic upgrade head
python -m app.bootstrap                        # seed + demo publish (idempotent)
uvicorn app.main:app --reload                  # :8000

# CMS / Viewer (in separate shells)
cd cms    && npm install && npm run dev         # :5173
cd viewer && npm install && npm run dev         # :5174
```

### GitHub Codespaces

A `.devcontainer/` is included (Docker-in-Docker + Python 3.11 + Node 20). Create a Codespace on this repo, then in its terminal:

```bash
docker compose up --build
```

Codespaces auto-forwards ports 8000 / 5173 / 5174 — open the **Viewer (5174)** and **CMS (5173)** from the *Ports* tab.

**One Codespaces gotcha:** in the browser-based editor, forwarded ports are served at `https://<name>-5174.app.github.dev`, so the UIs (which bake `VITE_API_BASE` at build time) can't reach the API at `http://localhost:8000`. Two ways to handle it:

- **Simplest — use VS Code Desktop.** "Open in VS Code Desktop" from the Codespace; local port-forwarding makes `localhost:8000/5173/5174` work exactly as documented above.
- **Browser editor** — in the *Ports* tab set **port 8000 visibility to Public**, copy its forwarded URL, then rebuild the UIs pointing at it:
  ```bash
  API_URL="https://<your-codespace>-8000.app.github.dev"
  docker compose build --build-arg VITE_API_BASE="$API_URL" cms viewer
  # also set the API's browser-facing media + CORS to that host:
  MEDIA_BASE_URL="$API_URL/media" CORS_ORIGINS="*" docker compose up
  ```

### Tests

```bash
cd backend && pytest -q          # 36 tests
```

---

## First-boot behaviour (important)

The seed data ships with two deliberate defects, both handled honestly rather than silently cleaned:

1. **A duplicate `(content_group, language)` row** (`ep_9001` duplicates `ep_0004`). The importer keeps the first, **skips** the duplicate, and records it in the seed report — mirroring a real idempotent ingest. The DB unique constraint backs this up.
2. **`ep_0036` is `published` but has no artwork.** This **correctly blocks a clean publish** — so out of the box `/catalog` would 404 and the viewer would show "nothing published yet." That is the correct behaviour, and I didn't want to hide it *or* ship an empty demo.

**Decision:** the container bootstrap (`app/bootstrap.py`) prints the validation report *first* (so the block is visible in logs), then applies **exactly the fix the report tells an editor to make** — uploads the three sample images to `ep_0036` through the real `validate_artwork` + storage path — and publishes. Flip `PEBLO_DEMO_PUBLISH=0` to skip the fix and experience the real gate. `rhyme-rangers` (draft, no section) is intentionally left unpublished; it appears in the CMS but never in the catalogue. A third quirk — the episode title *"The Lost Kite"* is reused across 8 shows — is real data, not a bug: searching `kite` correctly returns all published shows that have such an episode, each annotated `matched_on: ["episode"]`.

---

## Decisions & trade-offs

- **Publish writes a versioned snapshot, then atomically swaps a pointer** — never overwrites the live file. (Details in [Part E §1](#1-atomic-publishing).)
- **Season 0 = trailers** is modelled as a normal season row with an `is_trailer` flag, so the number `0` never leaks into UI logic; the viewer surfaces trailers separately, never as a season.
- **`content_group` collapse** happens in the publish job, producing one entry with a `languages` list and per-language `duration_seconds`.
- **Roles enforced at the endpoint layer** via FastAPI dependencies: every `/admin/*` route needs `editor`; `POST /admin/catalog/publish` needs `admin` (editors get a `403` with a readable reason). The viewer carries no token and calls only `/catalog` + `/catalog/search`.
- **Artwork validation returns *all* problems at once** (shape + size + dimensions), phrased for a non-engineer, e.g. *"Wrong shape for the poster: it should be 2:3 (about 600×900), but this image is 900×900."*
- **Reference data (`sections`/`categories`/`languages`/artwork specs) lives in one file** (`reference.json`), served at `GET /reference`, read by both UIs — allowed values are defined once.
- **SQLite for tests, Postgres for real.** The same models/migration run on both; tests use SQLite + a temp dir for hermetic speed (no external services in CI).

### Time spent (~15.25 h)

| Part | ~Time |
|---|---|
| A — Backend (schema, upload, publish, search, auth, tests) | 6.0 h |
| B — CMS | 4 h |
| C — Viewer | 1.25 h |
| D — Pipeline & operability | 3 h |
| E — Written + verification pass | 1 h |

---

# Part E — Written

### 1. Atomic publishing

Publishing is a **versioned-write-then-pointer-swap**, never an in-place overwrite:

1. **Validate first.** If anything blocks, record a `blocked` publish run and stop — the live catalogue is never touched.
2. Build the catalogue as an in-memory dict, **deterministically ordered** (sections in reference order; shows by title; episodes by number; languages sorted).
3. Write it to an **immutable, versioned key** `catalog/runs/{run_id}.json`.
4. **Atomically swap** the live pointer `catalog/current.json` to the new bytes via `storage.put_atomic`. On local disk that's write-temp-file → `fsync` → `os.replace` (atomic within a filesystem on POSIX). On R2/S3 a single `PUT` is already atomic at the object level.
5. Record the run (who, when, counts, outcome).

**If the process dies mid-publish:** a reader hitting `/catalog` always sees a *complete* file — either the previous one or the new one, never a partial. If death happens before step 4, the pointer still references the old catalogue (the half-written temp file is discarded on local disk; an incomplete R2 multipart is never visible). If after step 4, the new catalogue is fully live and durable (`fsync`). The DB `publish_run` row may be left as `failed`, which is the honest record of the attempt. Because the versioned snapshot from step 3 is immutable, any past run is still on disk — the basis for rollback (a documented stretch goal).

### 2. Storage abstraction → moving to R2

Everything depends only on a small `Storage` protocol (`put`, `put_atomic`, `get`, `exists`, `delete`, `url`). A factory (`get_storage()`) returns `LocalStorage` or `R2Storage` based on `STORAGE_BACKEND`. **To move from local disk to Cloudflare R2, nothing in the routers/services changes** — you set env vars: `STORAGE_BACKEND=r2`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, and `R2_PUBLIC_BASE_URL` (the CDN/bucket host browsers fetch artwork from). `R2Storage` is already written (boto3, S3-compatible; `put_atomic` = `put` since object PUT is atomic). The only real-world follow-ups are operational, not code: point `MEDIA_BASE_URL`/`R2_PUBLIC_BASE_URL` at the public bucket/CDN, set bucket CORS for the viewer origin, and stop mounting the local `/media` static route.

### 3. Search — how, scale limit, next step

Search is **server-side** over published DB rows (never in the browser). `q` matches show title **OR** episode title **OR** category; `category`/`language`/`section` filters **compose** (AND) with `q` and each other. Title/section/language filters use indexed SQL (`ix_shows_title`, `ix_shows_status_section`, an `EXISTS`-style subquery on episode language); `q` substring and JSON-array `category` membership are currently evaluated in Python after load, because it's portable across SQLite/Postgres and the catalogue is small (8 shows / ~95 episodes). **It stops working at roughly the low tens of thousands of episodes** — the per-request full scan and Python-side filtering turn linear and slow. **Next step:** push it into Postgres — a `tsvector` full-text index (or `pg_trgm` for fuzzy substring) for `q`, a `jsonb @> ` GIN index (or a `show_categories` join table) for category — and paginate. Beyond that (millions), move to a dedicated search index (OpenSearch/Meilisearch) fed by the publish job.

### 4. Why serve a pre-published file instead of querying the DB per request?

The viewer is **read-heavy, edit-rare**, and correctness must be *stable*: a child browsing shouldn't see half-edited shows or an episode that an editor is mid-change. Publishing computes the expensive shape **once** — the `content_group` collapse, section grouping, deterministic ordering, artwork URL resolution — and serves it as a static blob that a CDN can cache indefinitely. It also cleanly separates "what editors are working on" (DB) from "what the public sees" (the published file), and makes publish an explicit, audited, reversible action rather than an emergent side effect of live queries. **Where it bites:** the catalogue is only as fresh as the last publish — a fix isn't visible until someone re-publishes (so publishing must be easy and observable, which the CMS publish page is for). It's also a whole-catalogue rebuild, which won't scale to very large catalogues without partitioning per section/segment or moving to incremental publishes. `GET /catalog/search` still hits the DB, so search reflects published rows without waiting on a rebuild.

### 5. What I left out, and AI-tool use

**Left out (deliberately, to stay in the time box):** real auth (static bearer tokens stand in for OIDC/JWT — roles *are* genuinely enforced, just not cryptographically verified); the stretch goals (catalogue rollback UI, publish dry-run diff, full change audit log) — though the versioned snapshots + `publish_runs` table are the foundation for all three; pagination in the viewer/search responses; image thumbnailing/transcoding on upload (we validate and store the original); and a real object store in the demo (local disk; R2 path is implemented but exercised only by unit tests). CMS/viewer styling is functional, not polished.

**AI tools:** I used an AI coding assistant (Claude) throughout as a pair — scaffolding boilerplate (Pydantic schemas, Alembic setup, React hooks), drafting editor-facing error copy, and rubber-ducking the atomic-publish and storage-abstraction designs. **Accepted:** the write-temp-`fsync`-`replace` atomicity approach, the `is_trailer` flag over magic-number checks, and the "return all validation errors at once" UX. **Rejected / corrected:** an early suggestion to overwrite `current.json` in place (defeats atomicity — replaced with versioned-write-then-swap); a client-side-only artwork size check (the CMS always POSTs to the server so validation can't be bypassed); and a tempting `lru_cache` on storage that caused a cross-test contamination bug I had to hunt down and fix in the test reset. The judgment calls and the verification (36 tests, end-to-end curl of every endpoint) are mine.

---

## Operability

- **Health:** `GET /health` returns `{"status":"ok","checks":{"database":true}}` and round-trips the DB. It deliberately does **not** fail when no catalogue is published — that's a valid empty state, not an outage. Used as the compose/CI health gate.
- **One thing I'd alert on:** **publish failure rate / publish success age** — specifically, alert if a `publish` run ends `failed` (as opposed to the expected `blocked`, which is editor-actionable), or if the newest successful run is older than the team's editing cadence. Rationale: the published file is the *only* thing the viewer serves, so a broken or stale publish is a direct, user-visible content outage even while the API and DB look perfectly healthy. Editor-caused `blocked` runs are normal and shown in the CMS, so they page nobody; `failed` runs indicate an infra/storage problem and should.
- **Secrets in production:** nothing sensitive is committed — `.env.example` holds only placeholders, and compose uses non-secret dev defaults. In production, `DATABASE_URL`, `R2_*` keys, and the auth tokens/OIDC client secret come from the platform's secret manager (AWS Secrets Manager / GCP Secret Manager / Vault) or GitHub **Environment secrets**, injected as env vars at deploy time and never baked into an image or a git history. The CI deploy job authenticates to the registry via **OIDC** (short-lived token, no stored registry password). Rotate tokens on a schedule; scope each to least privilege (the R2 key needs only object read/write on one bucket).

## CI

`.github/workflows/ci.yml`: **backend** (ruff lint + pytest on SQLite), **frontends** (typecheck + Vite build for CMS & viewer via a matrix), **images** (`docker compose build` then a smoke test that boots the stack and asserts `/health` is ok, `/catalog` has sections, and both UIs serve), and a **deploy** job that is written and explained (registry login via OIDC, tag+push immutable images, migrate as a release task, health-gated rollout, rollback by image tag) but gated to `main` and dry-run since there's no cloud target in this exercise.
```

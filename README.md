# GitLab-Integrated PM Tool

A read-heavy aggregation/reporting layer over GitLab's API — see [`PRD GitLab-Integrated PM Tool.md`](../Downloads/PRD%20GitLab-Integrated%20PM%20Tool.md) for the full spec. GitLab remains the single source of truth; this tool never forks task data.

## Structure

```
fe/            Next.js + TypeScript frontend (shadcn/ui, Tailwind, TanStack Query)
BE/            FastAPI backend (async SQLAlchemy, Alembic, Huey + Redis)
docker-compose.yml
```

## Current state (scaffold + auth + sync engine)

- GitLab OAuth2 login (`fe/src/app/page.tsx` → `BE /api/auth/login` → GitLab → `BE /api/auth/callback` → `fe/src/app/auth/complete`).
- Session cookie (JWT) issued after OAuth; GitLab access/refresh tokens encrypted at rest (Fernet).
- In-tool role (`engineer` / `manager` / `exec` / `admin`) stored per user; role decides landing page (`My Work` / `Team Board` / `Radar` / `Settings`).
- Placeholder pages for the four role-based homes — no data yet, just routing + shell.
- **Sync engine** (`BE/app/sync/`, `BE/app/workers/tasks.py`) per PRD Section 11:
  - Data model: `SyncedProject`, `Milestone`, `Label`, `WorkItem`, `MergeRequest`, `MergeRequestReviewer`, `ProjectMembership`, plus the locally-owned `BlockedFlag` / `Note` / `CheckIn` (Section 11.4/11.5).
  - GraphQL (Work Items API) reconciliation path, with a REST (classic Issues API) fallback for older self-hosted instances (`reconciliation.py` / `reconciliation_rest.py`), auto-detected via `GitLabClient.supports_work_items_api`.
  - Huey periodic task fans out one `reconcile_one_project` job per synced project, staggered across the 15-minute window, with per-project exponential backoff on GitLab 429s (Section 13.1).
  - Webhook receiver (`POST /api/webhooks/gitlab/{synced_project_id}`, `app/api/webhooks.py`) verifies a per-project secret token, then enqueues an immediate reconciliation of that project rather than hand-parsing each event shape.
  - `webhook_registration.py` has the register/unregister-webhook calls the (not-yet-built) admin "select projects to sync" screen will call.
  - GraphQL query field names (`app/sync/queries.py`) are written against GitLab's documented schema but **not yet validated against a live instance** — verify during setup per Section 5.2 step 1.
- **Admin setup** (`BE/app/api/admin.py`, `fe/src/app/settings/`) per PRD Section 5.2 steps 1–3 and 5:
  - The first person ever to sign in for a fresh deployment is auto-promoted to the `admin` in-tool role (bootstraps Section 5.2's "whoever sets the tool up").
  - `/settings` (Admin only, gated by `require_admin`): GitLab connection status, search-and-sync GitLab projects (creates the `SyncedProject`, detects Work Items API support, registers the webhook, kicks off an initial reconciliation — all best-effort with warnings surfaced rather than hard failures), unsync/resync, a members table with an in-tool role dropdown per person, and a health-rule thresholds form (Section 5.2 step 5's defaults, now admin-editable).
  - Label/status mapping (Section 5.2 step 4) is still not built — unmapped projects show raw GitLab labels, which the PRD says is an acceptable default.

Not yet built: label/status mapping UI, My Work / Team Board / Exec Radar data assembly, create/assign write-through, standups, notifications, health-rule (blocked/stale) *computation* (thresholds are stored and editable, but nothing evaluates them against work items yet).

## Local development

### 0. Postgres + Redis

If you're not running the whole stack via Docker Compose (step 4), start these two yourself:

```bash
docker run -d -p 5432:5432 -e POSTGRES_USER=pmtool -e POSTGRES_PASSWORD=pmtool -e POSTGRES_DB=pmtool postgres:16-alpine
docker run -d -p 6379:6379 redis:7-alpine
```

**Windows gotcha:** if you already have a native PostgreSQL service installed (check with
`Get-Service *postgres*`), it's likely already bound to `0.0.0.0:5432`, and the container above
will silently lose that port — `localhost:5432` will hit the native install instead, with
different credentials, and you'll see `asyncpg.exceptions.InvalidPasswordError` even though
your `.env` is correct. Either stop the native service, or just map the container to a free
port instead (e.g. `-p 5433:5432`) and set `DATABASE_URL`'s port to match in `BE/.env`.

### 1. Backend

```bash
cd BE
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # fill in GitLab OAuth app credentials, TOKEN_ENCRYPTION_KEY, GITLAB_SYNC_SERVICE_TOKEN
alembic upgrade head     # applies the existing migration in alembic/versions/
uvicorn app.main:app --reload
```

After changing a model, generate the next migration with `alembic revision --autogenerate -m "..."` (needs a running Postgres matching `DATABASE_URL`).

To run the sync worker locally:

```bash
huey_consumer app.workers.huey_app.huey
```

Generate a `TOKEN_ENCRYPTION_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

You'll need a GitLab OAuth application (Admin Area → Applications, or a group/user-owned one) with:

- Redirect URI: `http://localhost:8000/api/auth/callback`
- Scopes: `read_api`, `read_user` (add `api` later for write-through create/assign)

### 2. Frontend

```bash
cd fe
pnpm install
copy .env.example .env.local
pnpm dev
```

Visit `http://localhost:3000`.

### 3. Or run everything via Docker Compose

```bash
docker compose up --build
```

(Fill in `BE/.env` and `fe/.env` first — compose reads them via `env_file`.)

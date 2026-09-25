# Stanley

Stanley gives a company a clear, simple view of what everyone is working on and what is stuck, on top of
**self-hosted GitLab**. It is a read-heavy aggregation layer: **GitLab stays the single source of truth** for
work items, merge requests, milestones and labels. Stanley caches them, infers status from real GitLab state,
and offers a small set of write-through actions so managers and engineers don't have to leave the tool.

Engineers keep working in GitLab with no change in behaviour. Stanley exists for the people who find GitLab's own
boards and reports overwhelming: leadership, managers, and engineers who want a calmer personal dashboard.

> Section numbers such as "PRD 6.4" in code comments refer to the product spec this project was built from.

## What it does

Each person lands on a screen that fits their role. Roles are assigned inside Stanley and only change which screens
you see, never what you can do in GitLab (see [Permissions](#permissions)).

| Screen | For | What's there |
| --- | --- | --- |
| **My Work** | Engineers | Doing now / Up next / Waiting on someone else / Review requests / Watching, personal stats and an 8-week trend, a "needs you now" strip, your GitLab To-Do inbox, recent activity, an optional daily check-in, search and filters, watch and snooze |
| **Team Board** | Managers | One lane per person (not status columns), a "needs your attention" strip, filters by project, milestone and label, a flagged-only switch, click-through side panel with live GitLab description and comments, reassign, milestone changes |
| **Standups** | Managers | Everyone's optional check-ins for a day on one page, a blockers roll-up, follow specific people, quiet "no check-in" list |
| **Exec Radar** | Executives | In progress / blocked / in review / shipped this week, delivery trend chart, per-project health from milestones, blockers list, by-person view |
| **Settings** | Admins | GitLab connection, search and sync projects, member roles, health-rule thresholds, in-progress label |

Write actions, all executed in GitLab **as the signed-in user**: create a work item, reassign, comment (posted with a
small "Sent from Stanley" footer), request a review, link work items to merge requests (many-to-many), and set a
work item's milestone (project Maintainers and Owners only).

### Design principles

- **GitLab is the system of record.** Stanley never becomes a second place to manage tasks. Its own data is limited to:
  blocked reasons, watch and snooze choices, standup check-ins, follows, in-tool roles and settings.
- **Write-through, not write-around.** Every change is a real GitLab API call made with the acting user's own token.
- **Transparent inference.** "Stale", "blocked" and "flagged" come from thresholds an admin can see and edit, never a hidden score.
- **No new mandatory process for engineers.** Check-ins are optional, skipping is never flagged, and personal stats are shown only to that person. Nothing is based on hours or story points.

## Architecture

```
  Browser ──▶ Next.js (fe/) ──▶ FastAPI (BE/) ──▶ PostgreSQL
                                   │  ▲
                 GitLab OAuth2 ◀───┘  │  webhooks
                 (login, and writes   │
                  as the user)   GitLab ◀──▶ Huey worker ◀── Redis
                                        (service token: sync + reconciliation)
```

- **Frontend:** Next.js 16 (App Router) with TypeScript, Tailwind CSS v4, shadcn/ui (Base UI primitives), TanStack Query, Recharts.
- **Backend:** FastAPI (async), SQLAlchemy 2 + asyncpg, Alembic migrations.
- **Worker:** Huey on Redis runs webhook processing and reconciliation.
- **Data:** PostgreSQL.

### How sync works

1. **Webhooks** (issues, merge requests, pipelines) are registered per synced project and trigger an immediate re-sync of that project.
2. **Reconciliation** re-reads every active project every 15 minutes, staggered so projects aren't polled on the same tick, with exponential backoff on GitLab rate limits. Reconciliation always wins over webhook state.
3. The service token reads GitLab via **GraphQL (Work Items API)**, with a **REST fallback** for older instances.
4. Merge requests are linked to work items only through references GitLab itself shows (`Closes #12`, `Related to #12`, `#12` in the title or description). Stanley's Link and Unlink buttons write the same references, so the two never disagree.

Comments and full threads are never cached; they are read live, as you, when a panel opens.

## Repository layout

```
BE/                    FastAPI backend
  app/api/             HTTP routes (auth, admin, my work, team board, radar, standups, actions, webhooks)
  app/services/        Dashboard logic (buckets, stats, health rules, radar, standups)
  app/sync/            GitLab client, reconciliation (GraphQL + REST), webhooks, write-through mutations
  app/workers/         Huey tasks
  app/models/          SQLAlchemy models
  alembic/versions/    Database migrations
fe/                    Next.js frontend
  src/app/             Routes (my-work, team-board, standups, radar, settings)
  src/components/      Dashboard widgets, dialogs, shadcn/ui components
  src/lib/             API client and typed fetchers
docker-compose.yml     Postgres, Redis, backend, worker, frontend (see the note under "Docker Compose")
```

## Getting started

### Prerequisites

- Python 3.11+, Node.js 20+ and [pnpm](https://pnpm.io)
- Docker (for PostgreSQL and Redis), or your own instances
- A self-hosted GitLab you administer

### 1. Create the GitLab pieces

**OAuth application** (GitLab: Admin Area, Applications; or a user or group application)
- Redirect URI: `http://localhost:8000/api/auth/callback`
- Scopes: `api` and `read_user`. Write actions need `api`. A read-only deployment can use `read_api read_user`.

**Service account token** (used for background sync, never for user actions)
- Create a dedicated user, add it to the projects you want to sync, and create a personal access token with the `api` scope.
- Creating webhooks needs Maintainer on the project. With Reporter it can still read and sync, but webhooks won't register (sync then relies on the 15-minute poll).

### 2. Start PostgreSQL and Redis

```bash
docker run -d -p 5432:5432 -e POSTGRES_USER=pmtool -e POSTGRES_PASSWORD=pmtool -e POSTGRES_DB=pmtool postgres:16-alpine
docker run -d -p 6379:6379 redis:7-alpine
```

> **Windows:** if you have a native PostgreSQL service installed it may already own port 5432, so `localhost:5432` reaches the wrong server and you get `InvalidPasswordError`. Check with `Get-Service *postgres*`. Either stop it or map the container to another port (for example `-p 5433:5432`) and use that port in `DATABASE_URL`.

### 3. Backend

```bash
cd BE
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
```

Edit `BE/.env` (see [Configuration](#configuration)). Generate the encryption key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then migrate and run:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal, start the sync worker. Nothing syncs without it:

```bash
cd BE
huey_consumer app.workers.huey_app.huey
```

### 4. Frontend

```bash
cd fe
pnpm install
cp .env.example .env.local
pnpm dev
```

Open http://localhost:3000. If that port is busy Next.js picks another one; set `FRONTEND_BASE_URL` in `BE/.env` to match, or CORS will block the API.

### 5. First run

1. Click **Sign in with GitLab**. **The first person to sign in becomes the Admin.**
2. Go to **Settings**. GitLab connection should show *Connected*.
3. Search for a project and click **Sync**. Wait for "last synced" to appear (this needs the worker running).
4. Under **Members**, assign in-tool roles (Engineer, Manager, Exec, Admin). People appear once a synced project includes them.
5. Optionally set the health thresholds and an **in-progress label** (for example `status::doing`) so labelled items show under "Doing now".

## Configuration

`BE/.env`

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `development` or `production` (production makes cookies `secure`) |
| `APP_SECRET_KEY` | Signs session tokens. Use a long random string |
| `FRONTEND_BASE_URL` | Frontend origin, used for CORS and post-login redirect |
| `BACKEND_BASE_URL` | Public URL of this API. GitLab calls it for webhooks |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:port/db` |
| `REDIS_URL` | Redis used by Huey and duplicate-submit protection |
| `GITLAB_INSTANCE_URL` | Your GitLab base URL |
| `GITLAB_OAUTH_CLIENT_ID` / `GITLAB_OAUTH_CLIENT_SECRET` | From the OAuth application |
| `GITLAB_OAUTH_REDIRECT_URI` | Must match the OAuth application exactly |
| `GITLAB_OAUTH_SCOPES` | Default `api read_user` |
| `GITLAB_SYNC_SERVICE_TOKEN` | Service account token for background sync |
| `TOKEN_ENCRYPTION_KEY` | Fernet key. User GitLab tokens are encrypted at rest with it |
| `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` | Session settings (default HS256, 7 days) |

`fe/.env.local`

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Backend URL. Defaults to `http://localhost:8000` |

## Permissions

Two layers that must agree:

1. **GitLab permissions are the hard ceiling.** Stanley acts with each user's own OAuth token, so a user can never see or do more than their GitLab account allows.
2. **In-tool roles** (Engineer, Manager, Exec, Admin) only decide which screens you land on and who can read locally-owned data such as standups. They never grant extra GitLab access.

Stanley adds one stricter rule on top: changing a work item's **milestone** requires Maintainer or Owner on that project.

Tokens are refreshed silently when they expire. If a login was granted read-only scopes, write actions say so and explain how to fix it.

## Webhooks and networking

Stanley registers a webhook on each synced project pointing at `BACKEND_BASE_URL`. That URL must be reachable **from the GitLab server**:

- `localhost` from GitLab's point of view is GitLab itself, so a laptop backend can't receive webhooks directly. Deploy the backend somewhere GitLab can reach, or use a tunnel.
- GitLab blocks webhooks to private addresses by default. To allow them: Admin Area, Settings, Network, Outbound requests, then enable *Allow requests to the local network from webhooks and integrations*.
- If webhook registration fails, syncing still works through the 15-minute reconciliation. You'll just see changes with a delay.

## API overview

Interactive docs are served by FastAPI at `http://localhost:8000/docs`.

| Area | Routes |
| --- | --- |
| Auth | `/api/auth/login`, `/callback`, `/me`, `/logout` |
| Admin | `/api/admin/gitlab/*`, `/synced-projects`, `/members`, `/settings` |
| My Work | `/api/my-work`, `/api/my-work/overview`, `/api/todos`, `/api/check-ins/today`, `/api/work-items/{id}/preferences` |
| Team Board | `/api/team-board`, `/api/team-board/filters`, `/api/work-items/{id}/detail` |
| Standups | `/api/standups`, `/api/standups/follows/{person}` |
| Radar | `/api/radar` |
| Actions | `POST /api/work-items`, `/comment`, `/blocked`, `/unblock`, `PATCH /assignee`, `/milestone`, `/api/merge-requests/{id}/reviewers`, link and unlink merge requests |
| Webhooks | `POST /api/webhooks/gitlab/{project}` |

## Docker Compose

`docker-compose.yml` defines the whole stack (`docker compose up --build`, after creating `BE/.env`). It has **not been exercised end to end**; the flow documented above, running the services directly, is the tested path. Note that `NEXT_PUBLIC_*` variables are baked into the frontend at build time.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `getaddrinfo failed` running Alembic | `DATABASE_URL` uses the compose hostname `db`. Use `localhost` when running outside Docker |
| `InvalidPasswordError` on `localhost:5432` | Another PostgreSQL owns the port. See the Windows note in step 2 |
| Project stuck on "sync pending" | The worker isn't running, or the task failed. Check the `huey_consumer` output |
| `undefinedField` in the worker log | A GraphQL field name differs on your GitLab version. Adjust `BE/app/sync/queries.py` |
| Webhook registration 422 | GitLab is rejecting the URL. See [Webhooks and networking](#webhooks-and-networking) |
| Write actions say your login lacks `api` | Enable `api` on the OAuth app, set `GITLAB_OAUTH_SCOPES`, restart, **revoke Stanley** in GitLab under Preferences, Applications, then sign out and in |
| Browser shows CORS errors | `FRONTEND_BASE_URL` doesn't match the port the frontend is on, or the API returned a 500 |
| Everything is empty after linking changes | Resync each project so links rebuild from GitLab references |

## Known limitations

- Developed against a self-hosted GitLab with the Work Items API. GraphQL field names can differ on other versions.
- Each project sync reads the first 100 work items and 100 merge requests. Cursor pagination isn't implemented yet.
- There's no reporting-line data, so Team Board and Standups show everyone (Standups adds per-manager follows).
- Review turnaround and "changes requested" aren't available: GitLab doesn't give us when a review was requested, and only approvals are synced.
- "Watch" is Stanley-only and doesn't change GitLab subscriptions.
- Standup dates use UTC.
- Weekly digest, Slack and email notifications, and the Projects and People pages are not built.
- There is no automated test suite yet.

## Development notes

- After changing models: `alembic revision --autogenerate -m "message"` against a running Postgres, then review the migration.
- Type-check the frontend with `pnpm build`.
- Worker tasks use a short-lived, unpooled database connection per task, because each task runs in its own event loop.

## License

No license has been chosen yet.

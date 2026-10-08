# Equilibrium frontend

Next.js 15 (App Router) + TypeScript (strict) + Tailwind CSS v4. Standalone pnpm project.

## Requirements

- Node.js >= 22
- pnpm 11.8.0 (`corepack enable` picks it up from `packageManager`)

## Commands

| Command             | What it does                                        |
| ------------------- | --------------------------------------------------- |
| `pnpm install`      | Install dependencies (CI: `--frozen-lockfile`)      |
| `pnpm dev`          | Dev server on http://localhost:3000                 |
| `pnpm build`        | Production build (`output: "standalone"`)           |
| `pnpm start`        | Serve the production build                          |
| `pnpm lint`         | ESLint (flat config, next core-web-vitals + TS)     |
| `pnpm typecheck`    | `tsc --noEmit`                                      |
| `pnpm test`         | Vitest unit/component tests (`tests/unit`)          |
| `pnpm test:e2e`     | Playwright smoke test (`tests/e2e`, needs browsers) |
| `pnpm format`       | Prettier write                                      |
| `pnpm format:check` | Prettier check                                      |

E2E needs browsers once: `pnpm exec playwright install chromium`. It builds and starts
the app itself unless `E2E_BASE_URL` points at a running instance.

## Environment

Copy `.env.example` to `.env.local`. Both default to `http://localhost:8000` and are
validated in `src/lib/env.ts`.

| Variable                | Scope   | Purpose                                                                                         |
| ----------------------- | ------- | ----------------------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_API_URL`   | browser | Backend base URL (inlined at build time)                                                        |
| `BACKEND_URL`           | server  | Backend base URL for server components and route handlers (falls back to `NEXT_PUBLIC_API_URL`) |
| `NEXT_PUBLIC_USE_MOCKS` | both    | `false` switches the UI from `src/mocks` to the live API (inlined at build time)                |
| `NEXT_PUBLIC_APP_URL`   | browser | Primary Atlas URL used by calls to action from the marketing subdomain                          |
| `MARKETING_HOST`        | server  | Hostname that serves the marketing page, e.g. `home.mydomain.com`                               |

Live mode: `NEXT_PUBLIC_USE_MOCKS=false NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev`
(or set them before `pnpm build`). Every live call times out after 4 s (explain: 15 s). If the
backend is down, times out, answers 5xx or sends an unexpected shape, that call is answered from
the bundled demo data and the page shows "Showing cached demo data". A 404 is a real answer. The
browser calls `POST /api/v1/explain` directly, so the backend must allow the frontend origin (CORS).

## Routes and data

| Route             | What it shows                                                                                                                                                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/`               | Global search, example chips, Maria's three questions                                                                                                                                                    |
| `/search?q=`      | Results with type and match reason (exact, synonym, semantic); honest empty state                                                                                                                        |
| `/disease/[id]`   | Gap card first when there is no supported route; summary (cause, top symptoms, mechanism), then "Who shares this", "What exists", "What next"                                                            |
| `/path?from=&to=` | Chain of chips; solid = data, dashed = hypothesis; side panel with the edge evidence; "Explain this path"                                                                                                |
| `/actions/[id]`   | Patient action view: partners (why + cited edges), reusable vs what differs, next experiment (hypothesis), expert checklist, "Draft collaboration brief" (family/researcher, AI or template label, copy) |

Pages read data only through `AtlasClient` (`src/lib/api/client.ts`). Wire types are in
`src/lib/api/types.ts`, and zod schemas in `src/lib/api/schemas.ts` validate both the mock
JSON and live responses. Mocks are on by default: see `src/mocks/README.md`.

`GET /api/health` returns `{ "status": "ok", "backend": "ok" | "unreachable" }`, probing
`${BACKEND_URL}/health` with a 2 s timeout.

## Marketing subdomain

The Atlas continues to live on the primary frontend host. Set `MARKETING_HOST=home.mydomain.com`
and point that DNS record at the same Vercel deployment to serve the public marketing page there.
Set `NEXT_PUBLIC_APP_URL=https://mydomain.com` so the marketing calls to action return visitors to
the Atlas. Locally, `home.localhost:3000` routes to the marketing page when your browser resolves it.

## Docker

```sh
docker build -t equilibrium-frontend --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 .
docker run -p 3000:3000 -e BACKEND_URL=http://backend:8000 equilibrium-frontend
```

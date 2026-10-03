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

| Variable              | Scope   | Purpose                                  |
| --------------------- | ------- | ---------------------------------------- |
| `NEXT_PUBLIC_API_URL` | browser | Backend base URL (inlined at build time) |
| `BACKEND_URL`         | server  | Backend base URL used by route handlers  |

`GET /api/health` returns `{ "status": "ok", "backend": "ok" | "unreachable" }`, probing
`${BACKEND_URL}/health` with a 2 s timeout.

## Docker

```sh
docker build -t equilibrium-frontend --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 .
docker run -p 3000:3000 -e BACKEND_URL=http://backend:8000 equilibrium-frontend
```

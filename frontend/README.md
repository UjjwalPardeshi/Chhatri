# Chhatri console

The claims console for Chhatri (docs/SPEC.md §20). It has seven pages:

- **Overview** (`/`): the pitch-deck story (problem, how it works, the storm, WhatsApp journeys, humans in control, backtest proof, tech, roadmap, team). Its buttons load a scenario, seek to the right minute and open the live page. The storm and phone threads are fixed deck content; the backtest and integration badges are fetched live.
- **Live map** (`/live`): city heat map, triggered-zone card, KPIs, "Why Zone 9 got nothing" and the live feed
- **Claims** (`/claims`): officer queue with Approve and Decline
- **Merchant phone** (`/merchant/S-0142`): WhatsApp-style chat with voice, photos and the Soundbox strip
- **Audit** (`/audit`): the chain, with a "Verify chain" button
- **Backtest** (`/backtest`)
- **Policy** (`/policy`)

It is built with React 19, react-router 7, Leaflet 1.9 and Vite 8. The console is styled with plain CSS using the deck's design tokens. The merchant mini-app (`src/miniapp`) uses Tailwind CSS v4 and shadcn/ui scoped to its own `.miniapp` root, mapped onto the same tokens (ADR 0005, design system section 13). The Ubuntu and Noto Sans Devanagari fonts are self-hosted from `public/fonts`, so the console makes no requests to external font servers.

## Scripts (binding decision B7)

| Script | What it does |
| --- | --- |
| `npm run dev` | Dev server. `/api` is proxied to `VITE_API_URL` (default `http://localhost:8000`). |
| `npm run dev:mock` | Dev server in mock mode (`.env.mock` sets `VITE_MOCK=1`). |
| `npm run build` | `tsc -b && vite build`, output in `dist/`. |
| `npm run typecheck` | `tsc -b --noEmit`. |
| `npm run lint` | `oxlint --deny-warnings src tests`. |
| `npm run test` | `vitest run` (unit tests plus integration tests against the in-browser mock). |
| `npm run test:coverage` | The same, with v8 coverage. Thresholds: 90% lines and statements, 85% functions, 80% branches. |
| `npm run test:e2e` | Playwright (chromium) against a running backend and console. Set `CONSOLE_URL`, e.g. `http://localhost:5173`. |
| `npm run test:e2e:mock` | Playwright (chromium) against a mock-mode Vite server that it starts itself on `E2E_PORT` (default 4273). |

## Mock mode

Mock mode is on when `VITE_MOCK=1` is set, or when the URL has `?mock=1`. The `?mock=1` choice is remembered for the tab; `?mock=0` turns it off.

In mock mode the whole backend API from SPEC §19 runs in the browser (`src/mock/`). It uses:

- the same envelopes, error codes and SSE stream as the real backend, including `Last-Event-ID` resume
- the four scenarios
- deterministic ids starting at C-2291 and D-000001
- a sha256 audit chain

The monsoon replay reproduces the deck's golden numbers:

- Z7 37% for 46 shops, Z3 38%, Z12 47%
- triggers at 17:00; Anil gets ₹1,380 at 17:04 and his ₹600 instalment is paused at 17:05
- KPIs: 3 zones, 312 shops, 4 min

Every integration shows as SIMULATED, and the footer carries a "Mock data" badge.

A full page reload restarts the mock, so navigate in-app. For resilience checks, `window.__chhatriMock.outage(ms)` and `window.__chhatriMock.dropStreams()` cut the stream, and the header then shows "Reconnecting…".

## Basemap

The map uses CARTO Positron tiles. Since 2026, CARTO answers keyless requests with a watermark tile that reads "API KEY REQUIRED" (HTTP 200). Before loading tiles, the console fetches one probe tile and compares its sha256 with that watermark. If the probe returns the watermark, or tiles are unreachable, the map shows plain land with ward outlines and a note ("Basemap needs a CARTO key · wards shown" or "Basemap offline · wards shown").

To use keyed or other tiles, set `VITE_TILE_URL` to a Leaflet URL template, for example `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?api_key=...`.

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_URL` | `http://localhost:8000` | Dev proxy target for `/api` |
| `VITE_MOCK` | unset | `1` turns on mock mode |
| `VITE_TILE_URL` | CARTO Positron | Basemap tile template |
| `CONSOLE_URL` | unset | Console URL for `npm run test:e2e` |
| `E2E_PORT` | `4273` | Port of the mock server that `npm run test:e2e:mock` starts |

## Docker

`Dockerfile` builds `dist/` and serves it with unprivileged nginx on port 8080. `/api` and `/webhooks` are proxied to `${CHHATRI_BACKEND_UPSTREAM}` (default `backend:8000`), with SSE unbuffered (see `nginx.conf`).

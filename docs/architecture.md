# Architecture

## Application Mode

React/Vite single-page application (SPA) under `web/`.

## Stack

| Layer | Choice |
|-------|--------|
| Language | TypeScript |
| Framework | React 19 |
| Build | Vite |
| Styling | Tailwind CSS v4 |
| Fonts | Geist Sans, Geist Mono |
| Design tokens | Woven Dusk (see `docs/design-system.md`) |

## Frontend / Backend Boundary

Client-only SPA for now. No backend or API. Static build output from `npm run build`.

## Auth

None. Public access only.

## Deployment Target

Static hosting (Vercel, Netlify, or similar). See `docs/deployment.md`.

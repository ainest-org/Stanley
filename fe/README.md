# Stanley frontend

Next.js 16 (App Router), TypeScript, Tailwind CSS v4, shadcn/ui, TanStack Query and Recharts.

Setup, configuration and architecture are documented in the [root README](../README.md).

```bash
pnpm install
cp .env.example .env.local
pnpm dev      # http://localhost:3000
pnpm build    # production build and type check
```

Fonts are loaded with a CSS `@import` in `src/app/globals.css`.

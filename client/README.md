# PolicyKit web

The PolicyKit web app gives recruiters a pre-publication compliance workspace and gives policy administrators a small interface for versioned policy management.

## Local setup

1. Copy `.env.local.example` to `.env.local`.
2. Start the PolicyKit API on `http://localhost:8000`.
3. Install and start the web app:

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Checks

```bash
npm run typecheck
npm run build
```

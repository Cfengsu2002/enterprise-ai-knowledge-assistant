# Frontend

React (Vite) frontend for the Enterprise AI Knowledge Assistant. Sits alongside the `/app` backend.

## Setup

```bash
npm install
```

Optional: copy `.env.example` to `.env` and set `VITE_API_URL` if your backend runs on a different host/port (default: `http://localhost:8000`).

## Run

```bash
npm run dev
```

Open http://localhost:5173. Ensure the backend is running (e.g. `uvicorn app.main:app --reload` from project root with `app` on port 8000) so API calls to `/enterprise/{id}` work.

## Build

```bash
npm run build
```

Output is in `dist/`. For production, point `VITE_API_URL` at your deployed API and ensure the backend allows your frontend origin in CORS.

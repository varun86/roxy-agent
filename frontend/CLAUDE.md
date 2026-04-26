# Frontend

This is a Next.js 16.2.4 project with React 19 — APIs and conventions differ from earlier versions. Heed deprecation notices.

## Key Files
- `src/components/ChatContainer.tsx` — main chat UI, calls `/chat` and `/chat/stream`
- `src/lib/api.ts` — calls `GET /models` on load, then `POST /chat` or `POST /chat/stream`

## API Proxy
The frontend proxies to the backend at `http://localhost:8000`. Ensure the FastAPI backend is running before starting the frontend dev server.

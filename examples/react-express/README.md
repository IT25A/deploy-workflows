# React frontend and Express backend

One repository with two folders, for example:

```
my-project/
├── frontend/        React + Vite
├── backend/         Express
├── app.it25a.yml
└── .github/workflows/deploy.yml
```

The site is served at `https://<alias>.apps.it25a.de`, the backend at `https://<alias>.apps.it25a.de/api`. Because both share one address, the browser needs **no CORS** settings.

## Files

| File | Where | Notes |
|---|---|---|
| [`app.it25a.yml`](app.it25a.yml) | root | Describes the two services and the routing |
| [`frontend/Dockerfile`](frontend/Dockerfile) | `frontend/` | Builds the React app and serves the files |
| [`backend/Dockerfile`](backend/Dockerfile) | `backend/` | Starts the Express server |
| [`.dockerignore`](../../templates/.dockerignore) | `frontend/` **and** `backend/` | Copy it from `templates/` into both folders |

## What your code has to do

**Backend (Express).** All routes start with `/api`, because the prefix is kept. Listen on `PORT` (the Dockerfile sets `3000`) on all interfaces:

```js
import express from 'express';

const app = express();
app.set('trust proxy', true);          // the platform terminates HTTPS in front of your app
app.use(express.json());

app.get('/api/health', (_req, res) => res.json({ ok: true }));
app.get('/api/items', (_req, res) => res.json([{ id: 1, name: 'First item' }]));

const port = Number(process.env.PORT ?? 3001);   // 3001 on your computer, 3000 in the container
app.listen(port, '0.0.0.0', () => console.log(`listening on ${port}`));
```

`import` needs `"type": "module"` in `backend/package.json`; with `require` the Dockerfile works as well. `package.json` needs `"start": "node index.js"`.

**Frontend (React).** Call the backend with a path **without host name**, so it works on every address (production and previews):

```js
const items = await fetch('/api/items').then((r) => r.json());
```

For development on your computer, forward `/api` to your local backend in `frontend/vite.config.js`:

```js
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:3001' } },
});
```

## Storing data

The backend keeps no data between updates by itself. For an SQLite file see [`react-express-sqlite`](../react-express-sqlite/README.md), for PostgreSQL [`react-express-postgres`](../react-express-postgres/README.md).

## Stopping cleanly

When a new version replaces the old one, the old container receives `SIGTERM`. Finish the running requests and exit:

```js
const server = app.listen(port, '0.0.0.0', () => console.log(`listening on ${port}`));

process.on('SIGTERM', () => {
  server.close(() => process.exit(0));      // stop accepting connections, let running requests finish
  setTimeout(() => process.exit(1), 10_000); // give up after 10 seconds
});
```

## Health checks

Both Dockerfiles contain a `HEALTHCHECK`. The frontend answers on `/` by itself; the backend needs the route `/api/health` shown above. A new version only goes live when both answer. If one does not, the update is rolled back and the old version keeps running.

## Secrets

Uncomment the `secrets` line in `app.it25a.yml` and list the names, create each secret in GitHub (repository, *Settings, Secrets and variables, Actions*), and read them in the backend with `process.env.API_KEY`. Secrets belong into the **backend**, never into the frontend.

## Variant: separate addresses instead of `/api`

If you prefer `https://api-<alias>.apps.it25a.de` for the backend, use this `app.it25a.yml`. (Keep the `/api` prefix in the routes, or change the health check path in `backend/Dockerfile` when you remove it.) The frontend then needs to know the address, which is passed in when it is built:

```yaml
version: 1
services:
  web:
    build:
      context: ./frontend
      args:
        VITE_API_URL: "{{ url.api }}"      # https://api-<alias>.apps.it25a.de (previews: api-<alias>-pr<n>)
    port: 3000
    route: { host: "@" }
  api:
    build: ./backend
    port: 3000
    route: { host: api }
```

In the frontend you then call the backend with the full address:

```js
const items = await fetch(`${import.meta.env.VITE_API_URL}/items`).then((r) => r.json());
```

The backend must allow the frontend's address with CORS (`app.use(cors({ origin: process.env.FRONTEND_URL }))`, with `FRONTEND_URL: "{{ url.web }}"` under `environment:` of the `api` service). Routes are then `/items`, without the `/api` prefix.
The `/api` variant above is simpler; choose this one only if you need separate addresses.

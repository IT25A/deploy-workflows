# React, Express and SQLite

A React frontend and an Express backend in one repository. The backend keeps its data in an **SQLite file**.
Every update starts a new container and throws the old one away with all files inside, so the SQLite file lies in a *volume*: a folder that Docker keeps outside the container. It survives updates, restarts and new versions. The line `volumes: ["db-data:/data"]` of the backend in `app.it25a.yml` attaches it.

```
my-project/
├── frontend/        React + Vite
├── backend/         Express + better-sqlite3
├── app.it25a.yml
└── .github/workflows/deploy.yml
```

The site is served at `https://<alias>.apps.it25a.de`, the backend at `https://<alias>.apps.it25a.de/api`.

## Files

| File | Where | Notes |
|---|---|---|
| [`app.it25a.yml`](app.it25a.yml) | root | The two services, routing, the path of the database file (`DB_PATH`) and the volume `db-data` at `/data` |
| [`backend/Dockerfile`](backend/Dockerfile) | `backend/` | Starts the Express server; creates `/data` for the unprivileged user |
| [`frontend/Dockerfile`](frontend/Dockerfile) | `frontend/` | Builds the React app and serves the files |
| [`.dockerignore`](../../templates/.dockerignore) | `frontend/` **and** `backend/` | Copy it from `templates/` into both folders (it also keeps local `*.sqlite` files out of the image) |

## What your code has to do

**Backend.** Open the database at the path from the environment, with a local fallback for development, create the tables at startup and answer the health check. `better-sqlite3` must be under `dependencies`, and `package.json` needs `"type": "module"` and `"start": "node index.js"`:

```js
import express from 'express';
import Database from 'better-sqlite3';

const db = new Database(process.env.DB_PATH ?? './local.sqlite');   // /data/app.sqlite on the server
db.pragma('journal_mode = WAL');

// There is no separate setup step on the server: create the tables when the app starts.
db.exec(`CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)`);

const app = express();
app.use(express.json());

// Answers the health check of the Dockerfile. It also proves that the database file can be read.
app.get('/api/health', (_req, res) => {
  db.prepare('SELECT 1').get();
  res.json({ ok: true });
});

app.get('/api/items', (_req, res) => res.json(db.prepare('SELECT id, name FROM items ORDER BY id').all()));

app.post('/api/items', (req, res) => {
  const info = db.prepare('INSERT INTO items (name) VALUES (?)').run(req.body.name);
  res.status(201).json({ id: info.lastInsertRowid, name: req.body.name });
});

const port = Number(process.env.PORT ?? 3001);       // 3001 on your computer, 3000 in the container
const server = app.listen(port, '0.0.0.0', () => console.log(`listening on ${port}`));

process.on('SIGTERM', () => {                         // sent when a new version replaces this one
  server.close(() => { db.close(); process.exit(0); });
});
```

**Frontend.** Call the backend without a host name (`fetch('/api/items')`) and forward `/api` to your local backend in `frontend/vite.config.js`, exactly as in [`react-express`](../react-express/README.md).

## If the backend cannot create the file

The log of the *Deploy* job then shows `SQLITE_CANTOPEN`, `EACCES` or "permission denied" and the container is reported as unhealthy. The reason is almost always the owner of `/data`: the backend runs as the unprivileged user `node`, but a new volume belongs to `root` unless the folder exists in the image with the right owner. The Dockerfile in this folder does that with `RUN mkdir -p /data && chown node:node /data`. Check that this line comes **before** `USER node`; after `USER node` it fails with "Permission denied" in the build.

## Good to know

- **Every preview has its own, empty database**, deleted when the pull request is closed. Production data is never touched by a pull request.
- Production data stays when you deploy a new version. There is **no backup** yet: download or export what you cannot recreate.
- SQLite is meant for one instance of the backend. That is exactly what the platform runs.
- If the path of the file changes, change `DB_PATH`, the `mkdir`/`chown` in the Dockerfile and the volume path in `app.it25a.yml` together.

# React, Express and PostgreSQL

The most complete everyday setup: a React frontend, an Express backend and a PostgreSQL database, in one repository.

```
my-project/
├── frontend/        React + Vite
├── backend/         Express + pg
├── app.it25a.yml
├── compose.it25a.yml
└── .github/workflows/deploy.yml
```

The site is served at `https://<alias>.apps.it25a.de` and the backend at `https://<alias>.apps.it25a.de/api`. The database can only be reached by the backend, never from the internet.

## Files

| File | Where | Notes |
|---|---|---|
| [`app.it25a.yml`](app.it25a.yml) | root | The two services, routing, plain settings and the name of the secret |
| [`compose.it25a.yml`](compose.it25a.yml) | root | The database with its own name and user, a health check and a volume |
| [`frontend/Dockerfile`](frontend/Dockerfile) | `frontend/` | Builds the React app and serves the files |
| [`backend/Dockerfile`](backend/Dockerfile) | `backend/` | Starts the Express server, with a health check |
| [`.dockerignore`](../../templates/.dockerignore) | `frontend/` **and** `backend/` | Copy it from `templates/` into both folders |

## Set up your own names and the password

1. Choose a database name and user. Change them in **both** files: `DB_NAME`/`DB_USER` in `app.it25a.yml` and `POSTGRES_DB`/`POSTGRES_USER` in `compose.it25a.yml`.
2. Create the secret `DB_PASSWORD` in GitHub (repository, *Settings, Secrets and variables, Actions*). Use letters and digits.
3. The database is created with these values **the first time it starts**. Changing the password later in GitHub does not change the password inside an existing database. Decide before the first deployment.

## What your code has to do

**Backend.** Connect with the plain settings and the secret, create the tables at startup, and answer the health check. `package.json` needs `"type": "module"` and `"start": "node index.js"`.

```js
import express from 'express';
import pg from 'pg';

const pool = new pg.Pool({
  host: process.env.DB_HOST ?? 'localhost',
  port: Number(process.env.DB_PORT ?? 5432),
  database: process.env.DB_NAME ?? 'shop',
  user: process.env.DB_USER ?? 'shop_app',
  password: process.env.DB_PASSWORD ?? 'dev',      // the fallbacks are for your computer only
});

// There is no separate setup step on the server: create the tables when the app starts.
await pool.query(`CREATE TABLE IF NOT EXISTS items (id SERIAL PRIMARY KEY, name TEXT NOT NULL)`);

const app = express();
app.use(express.json());

// Answers the health check of the Dockerfile. It also proves that the database works.
app.get('/api/health', async (_req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ ok: true });
  } catch {
    res.status(503).json({ ok: false });
  }
});

app.get('/api/items', async (_req, res) => {
  const { rows } = await pool.query('SELECT id, name FROM items ORDER BY id');
  res.json(rows);
});

app.post('/api/items', async (req, res) => {
  const { rows } = await pool.query('INSERT INTO items (name) VALUES ($1) RETURNING id, name', [req.body.name]);
  res.status(201).json(rows[0]);
});

const port = Number(process.env.PORT ?? 3001);       // 3001 on your computer, 3000 in the container
app.listen(port, '0.0.0.0', () => console.log(`listening on ${port}`));
```

**Frontend.** Call the backend without a host name (`fetch('/api/items')`) and forward `/api` to your local backend in `frontend/vite.config.js`, exactly as in [`react-express`](../react-express/README.md).

**A database on your computer** for development:

```bash
docker run --rm --name shop-db -p 5432:5432 -e POSTGRES_DB=shop -e POSTGRES_USER=shop_app -e POSTGRES_PASSWORD=dev postgres:18
```

## Stopping cleanly and hardening

Handle `SIGTERM` as shown in [`react-express`](../react-express/README.md#stopping-cleanly) and close the pool afterwards (`await pool.end()`).
The Compose file also starts the backend with the recommended hardening options (`init`, `cap_drop`, `read_only`, see the overview in [`examples/README.md`](../README.md)); the Dockerfiles run as the unprivileged user `node`. The database keeps its default settings, because PostgreSQL has to write to its own folders.

## Good to know

- **The health checks protect the visitors.** The database reports ready with `pg_isready`, the backend starts afterwards, and the backend only counts as healthy when `/api/health` can reach the database. If a new version cannot connect, the update is rolled back and the old version keeps running.
- **Each preview has its own empty database**, and it is deleted when the pull request is closed. Production data is never touched by a pull request.
- The data of production is kept in the volume `db-data` and survives updates. There is **no backup** yet: export what you cannot recreate.
- The database user created by `POSTGRES_USER` is the administrator of this one database, which belongs to your app alone.

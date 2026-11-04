# SvelteKit with an SQLite database

SQLite keeps the whole database in **one file**. Every update starts a new container and throws the old one away with all files inside, so the file has to lie in a *volume*: a folder that Docker keeps outside the container. Your data then survives updates, restarts and new versions of the app. The line `volumes: ["app-data:/data"]` in `app.it25a.yml` is all it takes.

## Files

| File | Where | Notes |
|---|---|---|
| [`Dockerfile`](Dockerfile) | root | Builds the SvelteKit app and starts it |
| [`app.it25a.yml`](app.it25a.yml) | root | Port, address, `ORIGIN`, the path of the database file and the volume `app-data` at `/data` |
| [`.env.example`](.env.example) | root | Dummy values for development and for the build |
| [`.dockerignore`](../../templates/.dockerignore) | root | Copy it from `templates/` (it also keeps local `*.db` files out of the image) |

## What your code has to do

This example uses the explicit environment variables of SvelteKit 3 (`src/env.ts` and `$app/env/private`). The older `$env/dynamic/private` still works in SvelteKit 2 but is deprecated.

1. Use `@sveltejs/adapter-node` in `svelte.config.js`, and install the validation library: `npm install valibot`.
2. Declare the variables the app needs in `src/env.ts`. A value that is missing or invalid stops the app at start with a clear message:

   ```ts
   // src/env.ts
   import { defineEnvVars } from '@sveltejs/kit/env';
   import * as v from 'valibot';

   const url = (name: string) =>
     v.pipe(v.string(), v.regex(/^(https?):\/\/[^\s/$.?#].[^\s]*$/, `${name} must be a valid HTTP or HTTPS URL`));

   export const variables = defineEnvVars({
     ORIGIN: { schema: url('ORIGIN') },
     DATABASE_PATH: { schema: v.pipe(v.string(), v.minLength(1, 'DATABASE_PATH must not be empty')) },
     // Secrets look the same, for example:
     // SESSION_SECRET: { schema: v.pipe(v.string(), v.minLength(16, 'SESSION_SECRET must have at least 16 characters')) },
   });
   ```
3. Put a dummy value for **every** variable of `src/env.ts` into `.env.example` and commit it (see the file in this folder). SvelteKit checks the variables when it builds, and the Dockerfile copies this file to `.env` for the build only. It does not end up in the final image, and the dummy values are not used when the app runs. (The SvelteKit documentation also describes making variables optional while building with `building` from `$app/env`; the `.env.example` way needs no change in `src/env.ts`.)
4. Open the database at the path from the environment. `better-sqlite3` must be under `dependencies`:

   ```ts
   // src/lib/server/db.ts
   import Database from 'better-sqlite3';
   import { DATABASE_PATH } from '$app/env/private';

   const db = new Database(DATABASE_PATH);
   db.pragma('journal_mode = WAL');

   // Create the tables when the app starts; there is no separate setup step on the server.
   db.exec(`CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, text TEXT NOT NULL)`);

   export default db;
   ```
5. Add a route for the health check of the Dockerfile. It also proves that the database file can be read:

   ```ts
   // src/routes/health/+server.ts
   import db from '$lib/server/db';

   export function GET() {
     db.prepare('SELECT 1').get();
     return new Response('ok');
   }
   ```
   If a login hook (`handle` in `src/hooks.server.ts`) redirects visitors, exempt `/health`.

## Hardening

The Dockerfile runs the app as the unprivileged user `node` and prepares `/data` for it. The platform adds `init`, `cap_drop: [ALL]` and a grace period for stopping by itself. If you change the folder of the database, change `mkdir`/`chown` in the Dockerfile, `DATABASE_PATH` and the volume path in `app.it25a.yml` together.

## Good to know

- **Health check:** the Dockerfile asks `/health` every 10 seconds. A new version only replaces the old one when this route answers; otherwise the update is rolled back.
- `ORIGIN` is required behind a proxy. Without it SvelteKit rejects form submissions with "Cross-site POST form submissions are forbidden". The value `{{ url.app }}` in `app.it25a.yml` is filled in per deployment, so it is correct for previews as well.
- **Every preview has its own, empty database.** Production data is never touched by a pull request. If you need test data, create it at startup.
- Production data stays when you deploy a new version. When the **pull request is closed**, its preview and its data are deleted.
- There is **no backup** yet. Download the file or export the data if you cannot recreate it.
- SQLite is meant for one app instance. That is exactly what the platform runs.

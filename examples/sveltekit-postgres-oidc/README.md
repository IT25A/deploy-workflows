# SvelteKit with PostgreSQL and OpenID Connect

An app with its own database, a login through an OpenID Connect provider, and a mix of secret and plain settings. It uses the explicit environment variables of SvelteKit 3 (`src/env.ts` and `$app/env/private`).

## Files

| File | Where | Notes |
|---|---|---|
| [`Dockerfile`](Dockerfile) | root | Builds the SvelteKit app; at start it runs the migrations and then the server |
| [`it25a.yml`](it25a.yml) | root | The app, its plain settings (`environment`) and the names of its secrets |
| [`docker-compose.yml`](docker-compose.yml) | root | The PostgreSQL database with its own name and user, health check and volume |
| [`.env.example`](.env.example) | root | Dummy values for development and for the build |
| [`scripts/migrate.js`](scripts/migrate.js) | `scripts/` | Applies the SQL files from `migrations/` that are not applied yet |
| [`migrations/001_init.sql`](migrations/001_init.sql) | `migrations/` | The first version of the schema; add `002_...sql` for later changes |
| [`.dockerignore`](../../templates/.dockerignore) | root | Copy it from `templates/` |

## Secrets and plain settings: where does what go?

| Setting | Kind | Where it is defined |
|---|---|---|
| `OIDC_CLIENT_SECRET`, `AUTH_SECRET`, `POSTGRES_PASSWORD` | **secret** | Create in GitHub (repository, *Settings, Secrets and variables, Actions*), list the name under `secrets` in `it25a.yml` |
| `OIDC_ISSUER`, `OIDC_CLIENT_ID` | plain | `environment` in `it25a.yml` (visible in the repository, fine for non-secret values) |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` | plain | `environment` in `it25a.yml`; `POSTGRES_DB` and `POSTGRES_USER` **also** in `docker-compose.yml`, where the database is created with them |
| `ORIGIN` | plain, **different per deployment** | `environment` with `{{ url.app }}`, which the platform replaces with the address of production or of the preview |

The variables `POSTGRES_*` have the names that the PostgreSQL image itself uses, so there is one set of names for the app and the database. Choose a password with letters and digits only, for example the output of `openssl rand -hex 24`.

## What your code has to do

1. Use `@sveltejs/adapter-node`, and install `valibot` (validation), `pg` (database) and put `pg` under `dependencies`.
2. Declare **all** variables in `src/env.ts`. A value that is missing or invalid stops the app at start with a clear message:

   ```ts
   // src/env.ts
   import { defineEnvVars } from '@sveltejs/kit/env';
   import * as v from 'valibot';

   const identifier = (name: string) =>
     v.pipe(v.string(), v.regex(/^[A-Za-z0-9_-]+$/, `${name} must only contain letters, numbers, underscores and hyphens`));
   const hostname = (name: string) =>
     v.pipe(v.string(), v.regex(/^[A-Za-z0-9.-]+$/, `${name} must only contain letters, numbers, dots and hyphens`));
   const url = (name: string) =>
     v.pipe(v.string(), v.regex(/^(https?):\/\/[^\s/$.?#].[^\s]*$/, `${name} must be a valid HTTP or HTTPS URL`));
   const port = (name: string) =>
     v.pipe(
       v.string(),
       v.regex(/^[0-9]+$/, `${name} must only contain numbers`),
       v.check((value) => Number(value) <= 65535, `${name} must be 65535 or lower`)
     );
   const secret = (name: string, minLength: number) =>
     v.pipe(v.string(), v.minLength(minLength, `${name} must be at least ${minLength} characters long`));

   export const variables = defineEnvVars({
     ORIGIN: { schema: url('ORIGIN') },
     AUTH_SECRET: { schema: secret('AUTH_SECRET', 16) },
     OIDC_ISSUER: { schema: url('OIDC_ISSUER') },
     OIDC_CLIENT_ID: { schema: identifier('OIDC_CLIENT_ID') },
     OIDC_CLIENT_SECRET: { schema: secret('OIDC_CLIENT_SECRET', 16) },
     POSTGRES_HOST: { schema: hostname('POSTGRES_HOST') },
     POSTGRES_PORT: { schema: port('POSTGRES_PORT') },
     POSTGRES_DB: { schema: identifier('POSTGRES_DB') },
     POSTGRES_USER: { schema: identifier('POSTGRES_USER') },
     POSTGRES_PASSWORD: { schema: secret('POSTGRES_PASSWORD', 16) }
   });
   ```
   Because the checks do not allow empty values, **every variable needs a value already when the app is built**. That is what `.env.example` is for: commit it with a dummy value for each variable (secrets long enough to pass the checks). The Dockerfile copies it to `.env` in the build stage only. It does not end up in the final image, and the dummy values are not used when the app runs. (The SvelteKit documentation also describes making variables optional while building with `building` from `$app/env`; the `.env.example` way needs no change in `src/env.ts`.)
3. Import the variables where you need them:

   ```ts
   // src/lib/server/db.ts
   import pg from 'pg';
   import { POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD } from '$app/env/private';

   export const pool = new pg.Pool({
     host: POSTGRES_HOST,
     port: Number(POSTGRES_PORT),
     database: POSTGRES_DB,
     user: POSTGRES_USER,
     password: POSTGRES_PASSWORD
   });
   ```
   The same way for `ORIGIN`, `AUTH_SECRET` and the `OIDC_*` values in your login code. The redirect address that the identity provider must allow is `<ORIGIN>/auth/callback` (if that is the path of your callback route).
4. The tables are created **by the migrations**, not by the app: `scripts/migrate.js` runs at every start of the container (see the `CMD` of the Dockerfile) and applies the files in `migrations/` that are not applied yet. Write a new file for every change of the schema (`002_add_tags.sql`) and never edit a file that was already applied. If a migration fails, the container stops and the update is rolled back.

## Health check

The Dockerfile only opens a connection to the port, because the start page of an app with a login usually redirects to the identity provider and would not answer with status 200. The server starts after the migrations succeeded, so a reachable port already means that the database was reachable.
If you want a check that tests the database on every run, add a route and change the `HEALTHCHECK` to fetch `/health`, as in [`sveltekit-sqlite`](../sveltekit-sqlite/README.md). Exempt `/health` from your login hook:

```ts
// src/routes/health/+server.ts
import { pool } from '$lib/server/db';

export async function GET() {
  try {
    await pool.query('SELECT 1');
    return new Response('ok');
  } catch {
    return new Response('database unavailable', { status: 503 });
  }
}
```

## Hardening

The Dockerfile runs the app as the unprivileged user `node`, and `docker-compose.yml` adds `init`, `cap_drop`, `read_only` and a grace period for stopping to the app (see the overview in [`examples/README.md`](../README.md)).

## Good to know

- `docker-compose.yml` starts the database before the app (`depends_on` with a health check), so the migrations never meet a database that is not ready.
- **Own database name and user:** the database `notes` and the user `notes_app` are created the first time the database starts. Change them in **both** `it25a.yml` and `docker-compose.yml` **before** the first deployment. The password is also set only then: changing the secret in GitHub later does not change the password inside an existing database.
- The data of the database is kept in the volume `db-data` and survives updates. **Each preview has its own empty database**, which the migrations fill with the schema when the preview starts. There is no backup yet.
- **Login on previews:** the identity provider only accepts redirect addresses that are registered. A preview has its own address (`<alias>-pr<number>.apps.it25a.de`), so the login only works there if the provider allows it (for example with a wildcard). Register `https://<alias>.apps.it25a.de/auth/callback` for production and test the login there.
- **Not needed for course-internal apps:** if only course members may use the app, keep `"production_access": "course"` in the registry (the default). The platform then does the login and passes `It25a-User` and `It25a-Name` to your app (see [guide](../../docs/getting-started.md#apps-for-course-members-only)). That replaces the whole OpenID Connect part.
- Not tested on a real server yet: `scripts/migrate.js` (only its syntax was checked). Please try it with your project and report problems.

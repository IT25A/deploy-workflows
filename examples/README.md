# Examples

Complete, working starting points. Each folder looks like the **root of a repository**: copy the files to the same places in your project and adapt the few marked values.
Besides these files every project needs the same two things, which are not repeated in each folder:

- `.github/workflows/deploy.yml`: copy [`caller-deploy.yml`](caller-deploy.yml)
- the entry in [`apps-registry`](https://github.com/IT25A/apps-registry) (step 3 of the [guide](../docs/getting-started.md))

| My project is... | Example | Files you add |
|---|---|---|
| A **React** (or Vue, Svelte) frontend only, no server of my own | [`react-only/`](react-only/) | `Dockerfile` |
| A **React frontend with an Express backend** (two folders, one repository) | [`react-express/`](react-express/) | `it25a.yml`, a `Dockerfile` per folder |
| A **React frontend with an Express backend and an SQLite** database file | [`react-express-sqlite/`](react-express-sqlite/) | `it25a.yml`, `docker-compose.yml`, a `Dockerfile` per folder |
| A **React frontend, Express backend and PostgreSQL** database | [`react-express-postgres/`](react-express-postgres/) | `it25a.yml`, `docker-compose.yml`, a `Dockerfile` per folder |
| **SvelteKit with an SQLite** database file | [`sveltekit-sqlite/`](sveltekit-sqlite/) | `Dockerfile`, `it25a.yml`, `docker-compose.yml`, `.env.example` |
| **SvelteKit with PostgreSQL and OpenID Connect** login, with secrets and plain settings | [`sveltekit-postgres-oidc/`](sveltekit-postgres-oidc/) | `Dockerfile`, `it25a.yml`, `docker-compose.yml`, `.env.example`, `scripts/migrate.js`, `migrations/` |
| A **C++** (or any other language) program | [`cpp/`](cpp/) | `Dockerfile`, `it25a.yml` |

## What the examples show besides the minimum

- **Health checks:** every `Dockerfile` has a `HEALTHCHECK`. The deployment waits until the app answers; if a new version never becomes healthy, the update is rolled back and the old version keeps running. The check calls a route of your app (`/health`, `/api/health` or `/`), so the code snippets in each README show it. Apps with a login use a plain connection check instead, because their start page redirects. If you copy a Dockerfile but not the route, the deployment fails with an unhealthy container: add the route or delete the `HEALTHCHECK` lines.
- **Own database name and user** instead of the defaults, and a database health check that uses the names from the environment of the container.
- **Plain settings and secrets side by side**, and values that change with every deployment (`{{ url.app }}` for the public address, which differs between production and every preview).
- **SvelteKit 3 environment variables:** `src/env.ts` validates every setting when the app starts, and the Dockerfile builds with the dummy values from `.env.example`. The PostgreSQL example also runs database migrations at every start.
- **Volumes**, so data survives updates (SQLite file, PostgreSQL data).
- **Hardening:** the apps run as the unprivileged user `node` instead of root, and the Compose files drop all Linux capabilities (`cap_drop`), make the container's files read-only (`read_only`, with `/tmp` writable), start a small init process (`init`) and give running requests 20 seconds to finish when the container stops (`stop_grace_period`). If your app writes files outside `/tmp` and the volume, remove `read_only` or add a volume for that folder. **Every folder the app writes to must belong to `node`**: create it with `RUN mkdir -p ... && chown node:node ...` **before** the line `USER node`, otherwise the app fails with `EACCES` or `SQLITE_CANTOPEN`.
- **Stopping cleanly:** on every update the old container receives `SIGTERM`. Apps that react to it finish their requests and close database connections instead of being killed after the grace period (snippet in [`react-express`](react-express/README.md)).

Nothing fits exactly? Combine them. The pieces are independent: the database part of the SvelteKit example works for an Express backend as well, and the Dockerfile templates in [`../templates/`](../templates/) cover more frameworks.

## How these examples were checked

- **Checked automatically:** the `it25a.yml` files pass the same validation that the deploy workflow runs, and the Compose files pass the rules of the deployer (allowed keys, images and volumes). The files were also rendered with the deployer's own code for production and for previews.
- **Not tested on a real Docker yet:** building the Dockerfiles and starting the containers, and the code snippets in the READMEs. If a build fails in your project, the log of the *Build* stage shows what is missing. If an example itself is broken, please tell the maintainers.

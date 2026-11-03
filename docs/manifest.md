# App manifest `it25a.yml`

> New here? Start with the [step-by-step guide](getting-started.md). This page is the reference for all fields.

The manifest describes which services of your app are built, how they are reachable and which secrets they need.
It lives in the root of your repository. Without a manifest, zero-config mode applies.

## Three modes

| Mode | Present in the repository | Result |
|---|---|---|
| **A – Zero-config** | only a `Dockerfile` in the root | One service `app`, port 3000, reachable at `https://<alias>.apps.it25a.de` |
| **B – Manifest** | `it25a.yml` | Any number of services (maximum 10), all built from source; the platform generates the Compose file |
| **C – Manifest + Compose** | `it25a.yml` and `docker-compose.yml` | Additional services such as databases come from your Compose file |

Complete example projects are in [`examples/`](../examples/README.md). Your editor knows the schema if the first line of the file looks like this (in VS Code this needs the extension **YAML** by Red Hat, `redhat.vscode-yaml`; without it the line is just a comment):

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/IT25A/deploy-workflows/main/schema/it25a.schema.json
```

## Fields

| Field | Required | Meaning |
|---|---|---|
| `version` | yes | Always `1` |
| `compose` | no | Path to your Compose file (mode C) |
| `services.<name>` | yes | Name: lowercase letters, digits, hyphens; starts with a letter; max. 30 characters; must not start with `it25a-` (reserved) |
| `…build` | yes in mode B | Build context as a path (`./backend`) or an object with `context`, `dockerfile`, `target`, `args` |
| `…build.dockerfile` | no | Relative to the context, default `Dockerfile` |
| `…build.args` | no | Build arguments, placeholders allowed |
| `…port` | no | Port inside the container, default `3000` |
| `…route.host` | yes, if `route` is set | `@` = main domain, otherwise a prefix for `<prefix>-<alias>` |
| `…route.path` | no | Path prefix, for example `/api` |
| `…route.strip_prefix` | no | Remove the prefix before forwarding (only together with `path`) |
| `…environment` | no | Non-secret variables, placeholders allowed |
| `…secrets` | no | Names of GitHub secrets that are passed to the service as environment variables |

A service without `route` is not reachable from outside, but it is visible to the other services of the app.
In mode C, `build` may be omitted if the service is defined in the Compose file.

## Reachability

| `route` | Production | Preview (pull request number `<n>`) |
|---|---|---|
| `host: "@"` | `<alias>.apps.it25a.de` | `<alias>-pr<n>.apps.it25a.de` |
| `host: api` | `api-<alias>.apps.it25a.de` | `api-<alias>-pr<n>.apps.it25a.de` |
| `host: "@", path: /api` | `<alias>.apps.it25a.de/api` | `<alias>-pr<n>.apps.it25a.de/api` |

- Per host, at most one service without `path` is allowed (it accepts all remaining requests). Paths must be unique.
- The alias comes from the registry (`apps-registry`), not from the manifest.
- Apps restricted to course members receive the headers `It25a-User` (username of the university account, not the GitHub username) and `It25a-Name` (first and last name of the university account, URL-encoded) on every request, so they need no login of their own. Trust them only in apps that are set to `course`.
- Production apps and previews are reachable by course members only by default (`production_access`, `preview_access`). **We encourage you to set `production_access` to `public` once the app is finished**, so that more people can benefit from it.

## Placeholders

In `environment` and `build.args` you can have values filled in:

| Placeholder | Result (example, production) |
|---|---|
| `{{ url.api }}` | `https://api-myapp.apps.it25a.de`, or `https://myapp.apps.it25a.de/api` with path routing |
| `{{ host.api }}` | `api-myapp.apps.it25a.de` |
| `{{ alias }}` | `myapp` |

`url` and `host` need a service with `route`. The values are known before the build, so you can pass them to a frontend as a build argument (for example `PUBLIC_API_URL`).

## Variables in the Compose file (mode C)

A service may appear in **both** files: `it25a.yml` says how it is built and published (`build`, `route`, `environment`, `secrets`), the Compose file adds what only Compose can express (`volumes`, `depends_on`, `healthcheck`, more `environment`). The two are merged; see [`examples/sveltekit-sqlite`](../examples/sveltekit-sqlite/).

The platform fills in these variables in your Compose file before it starts (`$$` gives a literal `$`; a variable without a value and without a default is an error):

| Variable | Content |
|---|---|
| `${IMAGE_<SERVICE>}` | Image of the service, for example `${IMAGE_API}` (service name in uppercase, `-` becomes `_`) |
| `${URL_<SERVICE>}`, `${HOST_<SERVICE>}` | like the placeholders above, for services with `route` |
| `${ALIAS}` | Alias of the app |
| `${<SECRET>}` | every secret that any service declares under `secrets` |

Example `docker-compose.yml` (a complete project with a database is in [`examples/sveltekit-postgres-oidc`](../examples/sveltekit-postgres-oidc/)):

```yaml
services:
  api:
    image: ${IMAGE_API}
    depends_on: [db]
  db:
    image: postgres:18
    environment:
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
    volumes:
      - db-data:/var/lib/postgresql   # PostgreSQL 18 and newer; for 17 and older use /var/lib/postgresql/data

volumes:
  db-data:
```

The deployer validates your Compose file strictly. Not allowed are, among others, `privileged`, `ports`, host mounts, `docker.sock`, `network_mode` and custom routing labels.
The platform generates routing from `route`.

### Which images may I use?

Your own services use `${IMAGE_<SERVICE>}`. For everything else only **official images from Docker Hub** from a list on the server are allowed. Currently:

| Image | For | Data folder for the volume |
|---|---|---|
| `postgres` | PostgreSQL database | `/var/lib/postgresql` (version 18 and newer), `/var/lib/postgresql/data` (17 and older) |
| `mysql`, `mariadb` | MySQL / MariaDB database | `/var/lib/mysql` |
| `mongo` | MongoDB | `/data/db` |
| `redis`, `valkey` | key-value store, cache | `/data` |
| `memcached` | cache (keeps nothing on disk) | – |

- Write the image with a version tag, for example `postgres:18` or `redis:8`, not `latest`: an update of the database program should never happen by accident.
- Images from other users or registries (`someone/tool`, `ghcr.io/...`) are not allowed, and neither are other official images such as `nginx`. If you need another one, ask the maintainers; the list is a server setting.
- The error message of a rejected image names the images that are currently allowed.
- Every container, including the database, gets at most 512 MB of memory and half a CPU.

## Secrets

1. Create the secret in GitHub (repository, Settings, Secrets and variables, Actions) as a **repository secret**. Secrets that are stored in an environment (`preview`, `production`) are not guaranteed to reach the reusable workflow; use them only after you have tested it.
2. Add the name under `secrets` of the service.
3. The workflow passes on only the declared secrets. All others stay in GitHub.

Keep the list short: store only values that are really secret (passwords, keys). GitHub hides every secret value wherever it appears. If a value is part of the address of your app (the alias, `app`, `it25a`, ...), GitHub hides it in the address too and does not attach the preview link to the pull request. A database name or user such as `x-poll` is not a secret; put it under `environment`.

Names with the prefixes `IT25A_`, `GITHUB_`, `IMAGE_`, `URL_`, `HOST_`, `COMPOSE_`, `DOCKER_` as well as `FQDN`, `PROJECT_NAME`, `PATH` and `HOME` are reserved.

## Validation

You do not have to run anything yourself: the *Plan* stage of the deploy workflow validates `it25a.yml` on every push and pull request, before anything is built or started. Errors appear in its log and name the field that is wrong.
For hints while typing, add the `yaml-language-server` line from the top of this page to your file (VS Code with the YAML extension by Red Hat).

The check is the script `scripts/validate_manifest.py` in this repository. Only if you want to run it on your computer, clone `IT25A/deploy-workflows` and run:

```bash
pip install -r scripts/requirements.txt
python scripts/validate_manifest.py /path/to/your-repo/it25a.yml --repo-root /path/to/your-repo
```

## Images

The workflow builds every service with `build` and pushes it to `ghcr.io/<owner>/<repo>/<service>:<tag>`.
The tag is unique per commit (`main-<sha>` or `pr<number>-<sha>`), so the deployer can start the previous version again if an update fails.
Build layers are cached between runs (GitHub Actions cache, one cache per service).
The deployer pulls the images without a login, so the packages must be public: if the first deployment fails with "denied" or "unauthorized" while pulling,
open the package on GitHub (profile or organization, Packages) and set its visibility to public once.

# App manifest `it25a.yml`

The manifest describes which services of your app are built, how they are reachable and which secrets they need.
It lives in the root of your repository. Without a manifest, zero-config mode applies.

## Three modes

| Mode | Present in the repository | Result |
|---|---|---|
| **A – Zero-config** | only a `Dockerfile` in the root | One service `app`, port 3000, reachable at `https://<alias>.apps.it25a.de` |
| **B – Manifest** | `it25a.yml` | Any number of services (maximum 10), all built from source; the platform generates the Compose file |
| **C – Manifest + Compose** | `it25a.yml` and `docker-compose.yml` | Additional services such as databases come from your Compose file |

Examples are in `examples/`. Your editor knows the schema if the first line of the file looks like this:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/IT25A/deploy-workflows/main/schema/it25a.schema.json
```

## Fields

| Field | Required | Meaning |
|---|---|---|
| `version` | yes | Always `1` |
| `compose` | no | Path to your Compose file (mode C) |
| `services.<name>` | yes | Name: lowercase letters, digits, hyphens; starts with a letter; max. 30 characters |
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
- Production apps are public. Previews are reachable by course members only by default (setting `preview_access` in the registry).

## Placeholders

In `environment` and `build.args` you can have values filled in:

| Placeholder | Result (example, production) |
|---|---|
| `{{ url.api }}` | `https://api-myapp.apps.it25a.de`, or `https://myapp.apps.it25a.de/api` with path routing |
| `{{ host.api }}` | `api-myapp.apps.it25a.de` |
| `{{ alias }}` | `myapp` |

`url` and `host` need a service with `route`. The values are known before the build, so you can pass them to a frontend as a build argument (for example `PUBLIC_API_URL`).

## Variables in the Compose file (mode C)

The platform writes an `.env` file that Compose substitutes at startup:

| Variable | Content |
|---|---|
| `${IMAGE_<SERVICE>}` | Image of the service, for example `${IMAGE_API}` (service name in uppercase, `-` becomes `_`) |
| `${URL_<SERVICE>}`, `${HOST_<SERVICE>}` | like the placeholders above, for services with `route` |
| `${ALIAS}` | Alias of the app |
| `${<SECRET>}` | every secret that any service declares under `secrets` |

Example `docker-compose.yml` for the manifest `04-with-compose-db.yml`:

```yaml
services:
  api:
    image: ${IMAGE_API}
    depends_on: [db]
  db:
    image: postgres:17
    environment:
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
    volumes:
      - db-data:/var/lib/postgresql/data

volumes:
  db-data:
```

The deployer validates your Compose file strictly. Not allowed are, among others, `privileged`, `ports`, host mounts, `docker.sock`, `network_mode` and custom routing labels.
Which public images are allowed (for example `postgres`, `redis`) is defined by a list on the server. The platform generates routing from `route`.

## Secrets

1. Create the secret in GitHub (repository, Settings, Secrets and variables, Actions). To separate preview and production, use environments (`preview`, `production`).
2. Add the name under `secrets` of the service.
3. The workflow passes on only the declared secrets. All others stay in GitHub.

Names with the prefixes `IT25A_`, `GITHUB_`, `IMAGE_`, `URL_`, `HOST_`, `COMPOSE_`, `DOCKER_` as well as `FQDN`, `PROJECT_NAME`, `PATH` and `HOME` are reserved.

## Validate locally

```bash
pip install -r scripts/requirements.txt
python scripts/validate_manifest.py it25a.yml
```

The script checks the schema, build folders and Dockerfiles, routing conflicts and placeholders. The deploy workflow runs the same validation before the build.
# Getting started

This guide takes a repository from zero to a running app at `https://<alias>.apps.it25a.de`.
It should take about 15 minutes. Everything happens in GitHub; you never log in to a server.

## How it works

```
your repository ──push──► GitHub Actions ──builds images──► ghcr.io
                              │
                              └──signed request──► deployer (cd.it25a.de) ──► https://<alias>.apps.it25a.de
```

- Every push to `main` updates the production app.
- Every pull request gets its own preview at `https://<alias>-pr<number>.apps.it25a.de`. It is removed when the pull request is closed, or after 14 days.
- Only repositories listed in [`apps-registry`](https://github.com/IT25A/apps-registry) are allowed to deploy. A maintainer approves each entry.

## Before you start

- Your repository is in the organization `IT25A` and is **public**. Please create repositories directly in the organization. If you would rather use a personal repository, talk to the maintainers first; it is possible in agreed cases, but not by default. Private repositories are not supported.
- Your app runs in a Docker container and listens on **port 3000** (or you set another port in `it25a.yml`).
- Your app starts without any local files that are not in Git (use environment variables for configuration).

## Step 1: Add a Dockerfile

Put a `Dockerfile` in the root of the repository. Example for a Node.js app:

```dockerfile
FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .
ENV PORT=3000
EXPOSE 3000
CMD ["node", "index.js"]
```

Test it locally before you continue:

```bash
docker build -t myapp . && docker run --rm -p 3000:3000 myapp
```

An app with several services (frontend, backend, database) needs an [`it25a.yml`](manifest.md) as well. See the [examples](../examples/).

## Step 2: Register the repository

1. Open [`IT25A/apps-registry`](https://github.com/IT25A/apps-registry) and fork it.
2. In your fork, add an entry to `apps.json`. The key is `owner/repo`:

   ```json
   "IT25A/my-repo": {
     "alias": "myapp",
     "title": "My App",
     "description": "What the app does, in one or two sentences"
   }
   ```

   The alias becomes your address `myapp.apps.it25a.de`. Choose a short, meaningful name that nobody could confuse with another project.
3. Open a pull request. A check called "Validate registry" runs automatically; fix what it reports.
4. A maintainer reviews and merges. Wait for the merge before you continue with the deployment.

Useful options for the entry (all described in the [registry README](https://github.com/IT25A/apps-registry#fields)):

- `"production_access": "course"` – only course members can open the app (good while it is under development).
- `"preview_access": "public"` – previews are open to anyone instead of course members only.
- `"previews": false` – no previews.

## Step 3: Add the workflow

Copy [`examples/caller-deploy.yml`](../examples/caller-deploy.yml) to `.github/workflows/deploy.yml` in your repository and commit it. You do not have to change anything in it.

## Step 4: Secrets (only if the app needs them)

For passwords, API keys and similar values:

1. In your repository: *Settings, Secrets and variables, Actions, New repository secret*. Use a **repository secret**, not an environment secret.
2. Declare the name in `it25a.yml` under `secrets` of the service. Only declared secrets are passed on.
3. Read them in your app as environment variables **at runtime** (not at build time). In SvelteKit use `$env/dynamic/private`.

Never commit secrets to the repository.

## Step 5: Push and look

Push to `main` (or open a pull request). In the *Actions* tab you see the run:

1. **Plan** validates your configuration.
2. **Build** builds the image and pushes it to `ghcr.io`.
3. **Deploy** starts the app and prints the URL at the end of its log.

### First deployment: make the image public

The deployer pulls images without a login. After the **first** build, open your repository's *Packages* (on the organization's page, tab Packages), open each package and set its visibility to **public**. Then re-run the failed deploy job. This is needed once per service.

## Reading errors

The error is printed in the log of the *Deploy* job.

| Message contains | Meaning | What to do |
|---|---|---|
| `is not registered` | No approved registry entry for this repository | Finish step 2 and wait for the merge |
| `repository ID does not match` | The alias already belongs to another repository (also after deleting and recreating a repository) | Ask a maintainer |
| `Only public repositories` | The repository is private | Make it public |
| `denied` / `unauthorized` while pulling | The image package is still private | Set the package to public (see above) |
| `Preview environments are disabled` | `previews` is `false` in the registry | Change it in the registry or merge to `main` |
| manifest or Compose validation errors | Something in `it25a.yml` or `docker-compose.yml` is not allowed | Run `python scripts/validate_manifest.py it25a.yml` (see [manifest.md](manifest.md#validate-locally)) |

If an update fails, the previous version keeps running. A failed **first** deployment leaves nothing behind.

Pull requests from forks are skipped on purpose: GitHub gives them no secrets and no identity token. Work on branches of the repository itself.

## Course members only: login and identity

Apps and previews that are restricted to course members need no login code. Visitors see a short explanation, sign in with GitHub, and come back to the page they wanted. Your app receives two request headers:

| Header | Content |
|---|---|
| `It25a-User` | Username of the university account (not the GitHub username) |
| `It25a-Name` | First and last name from the university account, URL-encoded (use `decodeURIComponent` or `urllib.parse.unquote`) |

Trust these headers **only** if the app is restricted to course members. On a public app anyone can send them.

## Limits

| Topic | Limit |
|---|---|
| Resources per container | 512 MB memory, 0.5 CPU, 256 processes |
| Services per app | 10 |
| Previews per app | 3 open at the same time, 14 days lifetime |
| Releases kept for rollback | 3 |
| Databases | Allowed (mode C with Compose, approved images such as `postgres`); data lives in volumes on the server |

There are **no database backups yet**. Keep your own copy of data that you cannot recreate.

Apps are for course projects. Do not store personal data of third parties, and do not run anything that needs more than the limits above.

## Further reading

- [`manifest.md`](manifest.md): all fields of `it25a.yml`, routing, placeholders, Compose variables
- [`examples/`](../examples/): fullstack, split frontend/backend (subdomains or same domain), Compose with database
- [`apps-registry`](https://github.com/IT25A/apps-registry): registry fields and rules

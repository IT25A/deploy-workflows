# Publish your project

This guide takes a project from "works on my computer" to a running website at `https://<alias>.apps.it25a.de`.
You need a GitHub account in the organization and a project that runs. You do **not** need a server login, SSH, or your own domain.
Everything happens in GitHub and takes about 30 minutes the first time, and almost no time after that.

## The big picture

```
you push to GitHub ──► GitHub builds your app into a "container image" ──► the platform starts it ──► https://<alias>.apps.it25a.de
```

- Every push to the `main` branch updates your website.
- Every pull request gets its own test version (a *preview*) at `https://<alias>-pr<number>.apps.it25a.de`, which disappears when the pull request is closed.
- To make this work you add **three things** to your project: a `Dockerfile`, a workflow file, and an entry in a shared list (the registry). Details follow below.

## What do I need?

| What | Where | Needed? |
|---|---|---|
| `Dockerfile` | root of your repository | **Always.** It tells the platform how to build and start your app. |
| `.dockerignore` | root of your repository | Recommended. Keeps unwanted files out of the build. |
| `.github/workflows/deploy.yml` | your repository | **Always.** Copy it, do not change it. |
| Entry in `apps.json` | repository [`IT25A/apps-registry`](https://github.com/IT25A/apps-registry) | **Always.** A maintainer approves it. |
| `it25a.yml` | root of your repository | Only if: your app has **several parts** (for example frontend and backend), uses **a port other than 3000**, or needs **secrets** (passwords, API keys). |
| `docker-compose.yml` | root of your repository | Only if you need a **database** or another extra service. |
| GitHub secrets | repository settings | Only if the app has passwords or API keys. |

You do **not** need: a `docker-compose.yml` for a single app, a `.env` file in the repository, port mappings, or anything on a server.

## Step 0: Check your project

1. The repository is in the organization **`IT25A`** and is **public** (*Settings, General, Danger Zone, Change visibility*). Please create the repository directly in the organization. If you would rather use a personal repository, talk to the maintainers first.
2. The app **starts with one command** that works on a fresh computer (for example `npm start`), and all dependencies are listed in `package.json` or `requirements.txt`.
3. For Node.js: `package-lock.json` is committed to Git. (The build uses `npm ci`, which needs it.)
4. The app listens on **port 3000** on all network interfaces. Express: `app.listen(3000)`. Flask and FastAPI: see the templates in step 2.
5. Configuration comes from **environment variables**, not from files that are only on your computer (for example `.env`).

## Step 1: Which setup fits?

| Your project | What you add |
|---|---|
| **One app** (one repository, one start command, for example a SvelteKit app or an Express app that also serves its pages) | `Dockerfile`. Nothing else. Frontend only: [`react-only`](../examples/react-only/) |
| **One app with secrets** or a port other than 3000 | `Dockerfile` and a short `it25a.yml` (step 5). C++ or another language: [`cpp`](../examples/cpp/) |
| **Frontend and backend** in one repository | One `Dockerfile` per part, and an `it25a.yml`. Complete example: [`react-express`](../examples/react-express/) |
| **A database** | The above, plus a `docker-compose.yml`. Complete examples: [`sveltekit-sqlite`](../examples/sveltekit-sqlite/) (SQLite file in a volume), [`sveltekit-postgres-oidc`](../examples/sveltekit-postgres-oidc/) (PostgreSQL, secrets, login), [`react-express-postgres`](../examples/react-express-postgres/) (frontend, backend and database) |

Most projects start with the first row. **Every example is a complete set of files that you can copy** and adapt: see the [overview of the examples](../examples/README.md). Read on; the other rows only change step 2 and step 5.

## Step 2: Add a Dockerfile

### What is it and why do I need it?

The server does not know whether your project is written in Node.js or Python, which version you use, or how to start it.
A **Dockerfile** is a short text file with exactly these instructions: "start from a computer that has Node.js, copy my files into it, install the dependencies, and run this command".
GitHub follows these instructions to build a **container image**, a self-contained package of your app, and the platform starts that package. The image is the same everywhere, so "it works on my computer" becomes "it works on the server".

The file must be called exactly **`Dockerfile`** (capital D, no ending) and lies in the root of your repository, next to `package.json`.

### Create it

1. Open the folder [`templates/`](../templates/) and pick the file that matches your project (Node.js, SvelteKit, Vite frontend, FastAPI, Flask, ...).
2. Check the short list of things at the top of the file. Each template says what must be true in your project.
3. In your repository on GitHub: *Add file, Create new file*, name it `Dockerfile`, paste the content, commit. Do the same for [`templates/.dockerignore`](../templates/.dockerignore) (name: `.dockerignore`). Working locally in an editor and pushing works just as well.

### How to read a Dockerfile

```dockerfile
FROM node:22-alpine              # start from a small Linux with Node.js 22
WORKDIR /app                     # work in the folder /app inside the container
COPY package.json package-lock.json ./
RUN npm ci --omit=dev            # install the dependencies
COPY . .                         # copy the rest of your project
ENV PORT=3000                    # the app should listen on this port
CMD ["npm", "start"]             # the command that starts the app
```

You will rarely change more than the last line (the start command) and the port.

### Test it on your computer (optional)

If you have Docker installed:

```bash
docker build -t myapp .
docker run --rm -p 3000:3000 myapp
```

Then open `http://localhost:3000`. If you do not have Docker, skip this: the pull request in step 6 builds your app on GitHub and shows you the same errors in the log.

### Typical mistakes

| Problem | Solution |
|---|---|
| The page does not load, but the log shows no error | The app listens only on `localhost`/`127.0.0.1`. It must listen on all interfaces (`0.0.0.0`) and on port 3000. |
| Build fails at `npm ci` | `package-lock.json` is missing in Git, or it does not match `package.json`. Run `npm install` locally and commit the lock file. |
| `npm start` is missing | Add `"start": "node index.js"` (your start file) under `scripts` in `package.json`. |
| The Dockerfile is not found | The file name is spelled wrong (`dockerfile`, `Dockerfile.txt`) or it is not in the root. |
| The app needs a `.env` file | Files like `.env` are not part of the build. Read the values from environment variables and use secrets (step 5). |

## Step 3: Register the repository

Only repositories on an approved list can be deployed. You request the entry with a pull request; you do not need Git on your computer for this.

1. Open [`apps.json` in `IT25A/apps-registry`](https://github.com/IT25A/apps-registry/blob/main/apps.json) and click the pencil (*Edit this file*). GitHub creates your own copy (a *fork*) automatically.
2. Add an entry. The key is `organization/repository`:

   ```json
   "IT25A/my-repo": {
     "alias": "myapp",
     "title": "My App",
     "description": "What the app does, in one or two sentences"
   }
   ```

   - Between two entries there is a **comma**; after the last entry there is **none**.
   - The `alias` becomes your address `myapp.apps.it25a.de`. Use lowercase letters, digits and single hyphens. Choose a short name that nobody could confuse with another project.
   - The description is visible to all course members.
3. Click *Commit changes*, then *Propose changes* and *Create pull request*.
4. A check called "Validate registry" runs automatically and shows what is wrong, if anything. Fix it by editing the file again in your copy; the pull request updates itself.
5. A maintainer reviews and merges. **Wait for the merge** before you continue with the first deployment.

Optional settings for the entry (full list in the [registry README](https://github.com/IT25A/apps-registry#fields)):

- `"production_access": "course"`: only course members can open the app. Recommended while the project is under development.
- `"preview_access": "public"`: previews are open to everyone instead of course members only.
- `"previews": false`: no previews.

## Step 4: Add the workflow

The workflow is the part that builds and publishes on every push. It is the same for everybody.

1. In your repository: *Add file, Create new file*, name it **`.github/workflows/deploy.yml`** (typing the slashes creates the folders).
2. Paste the content of [`examples/caller-deploy.yml`](../examples/caller-deploy.yml) and commit it. Do not change anything.

## Step 5: Secrets and `it25a.yml` (only if needed)

Skip this step if your app needs neither secrets nor a special port.

**Secrets** are values that must not be in Git: database passwords, API keys, session secrets.

1. In your repository: *Settings, Secrets and variables, Actions, New repository secret*. Use a **repository secret**, not an environment secret.
2. Create a file `it25a.yml` in the root of your repository. For one app with a secret it looks like this:

   ```yaml
   version: 1
   services:
     app:
       build: .
       port: 3000
       route: { host: "@" }
       secrets: [SESSION_SECRET]
   ```

   - `build: .` means: the Dockerfile is in the root.
   - `port` is the port your app listens on.
   - `route: { host: "@" }` makes the app reachable at `<alias>.apps.it25a.de`. Without `route` the app runs but nobody can open it.
   - `secrets` lists the **names** of your GitHub secrets. Only listed secrets are passed on.
3. Your app reads each secret as an environment variable **at runtime** (Node.js: `process.env.SESSION_SECRET`; SvelteKit: `$env/dynamic/private`).

Several parts or a database? Start from an [example](../examples/README.md) and read [`manifest.md`](manifest.md).

## Step 6: First deployment

1. Push to `main` (or merge your pull request). Open the **Actions** tab of your repository and click the latest run.
2. The run has three stages: **Plan** checks your files, **Build** builds the image, **Deploy** starts the app. At the end of *Deploy* the address of your app is printed.
3. **Only the first time**: the platform downloads your image without a login, so each image must be public.
   Open `https://github.com/orgs/IT25A/packages`, click your package, *Package settings*, scroll to the *Danger Zone*, *Change visibility*, *Public*.
   Then go back to the failed run and click *Re-run failed jobs*. (If the first run failed at *Deploy* with `denied` or `unauthorized`, this is the reason.) With several services this has to be done for each one.

Open the address. The first start can take a few seconds.

## Everyday work

- **Update the live site:** merge to `main`. A failed update never breaks the running version; the previous one keeps running.
- **Try changes safely:** create a branch and a pull request. Within a few minutes the pull request shows a *View deployment* button with the preview address. Only course members can open previews unless you set `preview_access` to `public`. Close or merge the pull request and the preview disappears.
- **Pull requests from forks** are skipped on purpose (GitHub gives them no secrets). Work on branches of the repository itself.
- **Change the address, title or description:** edit your entry in `apps-registry` with a pull request.

## Something went wrong

Every message appears in the log of the **Deploy** job (Actions tab, click the run, click the job).

| The message contains | Meaning | What to do |
|---|---|---|
| `is not registered` | There is no approved registry entry yet | Finish step 3 and wait for the merge |
| `repository ID does not match` | The alias already belongs to another repository (also after deleting and recreating a repository) | Ask a maintainer |
| `Only public repositories` | The repository is private | Make it public |
| `denied` / `unauthorized` while pulling | The image is still private | Step 6, point 3 |
| `Preview environments are disabled` | `previews` is `false` in the registry | Change it there, or merge to `main` |
| An error in **Plan** about `it25a.yml` or the Compose file | Something in your configuration is not allowed | Read the message; it names the line. Fix the file and push again |
| `unhealthy` | The Dockerfile has a `HEALTHCHECK`, but your app does not answer on the route it asks (for example `/health`) | Add the route (see the example's README) or remove the `HEALTHCHECK` lines. The old version keeps running meanwhile |
| The **Build** stage fails | The Dockerfile or the app build is broken | Read the log of the failing step; it is the same output as `docker build` on your computer |

**You do not have to check your configuration locally.** The *Plan* stage validates `it25a.yml` on every push and pull request before anything is built or started, and the registry pull request has its own check.
If you use VS Code with the YAML extension by Red Hat, add this line at the top of `it25a.yml` for live hints while typing:
`# yaml-language-server: $schema=https://raw.githubusercontent.com/IT25A/deploy-workflows/main/schema/it25a.schema.json`

A failed **first** deployment leaves nothing behind, so you can simply fix and push again.

## Apps for course members only

If you set `"production_access": "course"` (and for previews by default), visitors first see a short explanation, sign in, and come back to the page they wanted. Your app needs no login code. It receives two request headers:

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
| Databases | Allowed (with `docker-compose.yml`, approved images such as `postgres`); the data lives in volumes on the server |

There are **no database backups yet**. Keep your own copy of data that you cannot recreate.
Apps are for course projects. Do not store personal data of third parties.

## Checklist

- [ ] Repository is in `IT25A` and public
- [ ] `Dockerfile` and `.dockerignore` are in the root
- [ ] `.github/workflows/deploy.yml` exists
- [ ] Registry pull request is merged
- [ ] Secrets are created and listed in `it25a.yml` (if needed)
- [ ] Image is set to public after the first build
- [ ] The address from the *Deploy* log opens

## Further reading

- [`templates/`](../templates/): Dockerfiles for common frameworks
- [`manifest.md`](manifest.md): all fields of `it25a.yml`, routing, placeholders, Compose variables
- [`examples/`](../examples/README.md): complete projects (React, React and Express, with PostgreSQL, SvelteKit with SQLite or PostgreSQL and login, C++)
- [`apps-registry`](https://github.com/IT25A/apps-registry): registry fields and rules

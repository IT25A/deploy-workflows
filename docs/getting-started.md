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
| `app.it25a.yml` (or `.yaml`) | root of your repository | Only if: your app has **several parts** (for example frontend and backend), uses **a port other than 3000**, or needs **secrets** (passwords, API keys). |
| `compose.it25a.yml` | root of your repository | Only if you need a **database in its own container** (PostgreSQL, Redis, ...). |
| GitHub secrets | repository settings | Only if the app has passwords or API keys. |

You do **not** need: a `compose.it25a.yml` for an app without a database server (a SQLite file or uploads only need `volumes` in `app.it25a.yml`), a `.env` file with real values in the repository, port mappings, or anything on a server.

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
| **One app with secrets** or a port other than 3000 | `Dockerfile` and a short `app.it25a.yml` (step 5). C++ or another language: [`cpp`](../examples/cpp/) |
| **Frontend and backend** in one repository | One `Dockerfile` per part, and an `app.it25a.yml`. Complete example: [`react-express`](../examples/react-express/) |
| **SQLite** (or any other file the app writes and that must stay) | The above, **plus `volumes`** in `app.it25a.yml`, which attaches a folder that survives updates. Complete examples: [`sveltekit-sqlite`](../examples/sveltekit-sqlite/), [`react-express-sqlite`](../examples/react-express-sqlite/) |
| **A database of its own** (PostgreSQL, Redis, ...) | The above, plus a `compose.it25a.yml` that starts the database. Complete examples: [`sveltekit-postgres-oidc`](../examples/sveltekit-postgres-oidc/) (PostgreSQL, secrets, login), [`react-express-postgres`](../examples/react-express-postgres/) (frontend, backend and database) |

> **Why does SQLite need `volumes`?** Every update starts a **new container** and throws the old one away, together with every file that the app wrote inside it. A SQLite database is just a file, so without more it would be empty after each update. `volumes: ["data:/data"]` in `app.it25a.yml` attaches a **volume**: a folder that lives outside the container and survives updates, restarts and new versions. Your app stores the database file there. The same applies to uploaded files. A real database server such as PostgreSQL runs in its own container and needs such a volume too, in its `compose.it25a.yml`.

> **Your `compose.it25a.yml` is not a complete Compose file.** The platform merges it with `app.it25a.yml` into one Compose file on the server. That is why a service of your own may have only `depends_on` or `read_only` and no `image` or `build` in it: the platform adds the image it built. Use the example files as they are. `docker compose up` does not work with this file alone on your computer, and that is fine.

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
# Start from a small Linux that already has Node.js 26 (the current long-term support version).
FROM node:26-alpine

# Work in the folder /app inside the container (it is created if it does not exist).
WORKDIR /app

# Copy ONLY the two package files into the container first. The first path is a file in your
# repository, the last one is the destination in the container ("./" is the current folder /app).
COPY package.json package-lock.json ./

# Install the dependencies that these two files list.
RUN npm ci --omit=dev

# Now copy everything else: your source code and all other files of the project.
# (Files listed in .dockerignore, for example node_modules, are left out.)
COPY . .

# The app should listen on this port.
ENV PORT=3000

# The command that starts the app.
CMD ["npm", "start"]
```

(Comments in a Dockerfile must be on their own line starting with `#`. A `#` behind an instruction is not a comment and breaks the build.)

**Why are there two `COPY` lines?** Docker remembers the result of every line (a *layer*) and reuses it when nothing it depends on has changed. Installing the dependencies is the slow part. If only the two package files are copied before `npm ci`, Docker repeats the installation only when you change your dependencies; when you change a source file, only the last `COPY` runs again. In bigger projects the last `COPY` often copies only selected folders (`COPY src ./src`), or the project is built first and only the result is copied, as in the SvelteKit template.

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
| The app cannot write a file: `EACCES`, `Permission denied`, `SQLITE_CANTOPEN`, the container is "unhealthy" | The container runs as the unprivileged user `node`, who may only write to folders that belong to `node`. Create the folder in the Dockerfile **before** `USER node` (`RUN mkdir -p /data && chown node:node /data`) and attach a volume at that path (`volumes: ["data:/data"]` in `app.it25a.yml`). See [`react-express-sqlite`](../examples/react-express-sqlite/README.md). |
| The container stops with `Operation not permitted` | The platform removes all special Linux privileges from your container (for example to listen on a port below 1024 or to switch the user). Listen on a port above 1024, or set `cap_drop: []` for the service in your `compose.it25a.yml`. |
| Build fails at `mkdir` with "Permission denied" | The line stands **after** `USER node`. From there on every command runs as `node`. Move it above `USER node`. |
| The app needs a `.env` file | Files like `.env` are not part of the build. Read the values from environment variables and use secrets (step 5). |
| SvelteKit: the build fails because variables from `src/env.ts` are missing | SvelteKit 3 checks the variables when it builds. Commit a `.env.example` with harmless dummy values and let the Dockerfile copy it for the build, as in the [SvelteKit examples](../examples/sveltekit-sqlite/README.md). |

## Step 3: Register the repository

Only repositories on an approved list can be deployed. You request the entry with a form; you do not need Git on your computer for this.

1. Open the form [**Register an app**](https://github.com/IT25A/apps-registry/issues/new/choose) and fill it in (if the page says "404", ask the course representatives to give you access):

   | Field | Example |
   |---|---|
   | Repository | `IT25A/my-repo` |
   | Alias | `myapp` |
   | Title | `My App` |
   | Description | `A small tool to plan study groups` |

   - The `alias` becomes your address `myapp.apps.it25a.de`. Use lowercase letters, digits and single hyphens. Choose a short name that nobody could confuse with another project.
   - The title has at most 50 characters. The description has at most 250 characters and is visible to all course members.
2. Click *Submit new issue*. Within a minute a comment appears on your issue.
   - If something is wrong, the comment lists everything at once. Edit your issue and the check runs again.
   - If all is fine, a pull request is created and a maintainer reviews it.
3. **Wait until your issue is closed.** That means the maintainer merged the entry. Only then continue with the first deployment.

The other fields of the form:

- **Who may open the app**: *Course members only* means that visitors have to sign in with GitHub. It is the safe start while the project is under development. **When the app is finished, we encourage you to make it public** (*Everyone*), so that more people can benefit from it. Use the form [*Change an app*](https://github.com/IT25A/apps-registry/issues/new/choose) in `apps-registry` to switch it.
- **Previews for pull requests** and **Who may open the previews**: every open pull request gets its own test address. By default only course members can open previews.

(All fields are described in the [registry README](https://github.com/IT25A/apps-registry#fields).)

## Step 4: Add the workflow

The workflow is the part that builds and publishes on every push. It is the same for everybody.

1. In your repository: *Add file, Create new file*, name it **`.github/workflows/deploy.yml`** (typing the slashes creates the folders).
2. Paste the content of [`examples/caller-deploy.yml`](../examples/caller-deploy.yml) and commit it. Do not change anything.

## Step 5: `app.it25a.yml` and secrets (only if needed)

Skip this step if your app is **one container** (one `Dockerfile` in the root of the repository) that listens on port 3000 and needs neither secrets nor settings.

You need an `app.it25a.yml` as soon as one of these applies:

- the app listens on another port than 3000
- the app has **more than one part**, for example a frontend and a backend (also without secrets)
- the app needs a database or another service
- the app needs secrets or settings (`environment`)
- a part should be reachable under its own address or path (`/api`)

**Secrets** are values that must not be in Git: database passwords, API keys, session secrets.

1. In your repository: *Settings, Secrets and variables, Actions, New repository secret*. Use a **repository secret**, not an environment secret.
2. Create a file `app.it25a.yml` in the root of your repository. For one app with a secret and a setting it looks like this:

   ```yaml
   version: 1
   services:
     app:
       build: .
       port: 3000
       route: { host: "@" }
       environment:
         DATABASE_NAME: myapp
         PUBLIC_SITE_URL: "{{ url.app }}"
       secrets: [SESSION_SECRET]
   ```

   - `build: .` means: the Dockerfile is in the root.
   - `port` is the port your app listens on.
   - `route: { host: "@" }` makes the app reachable at `<alias>.apps.it25a.de`. Without `route` the app runs but nobody can open it.
   - `environment` sets variables that are **not secret**. Your app reads them like secrets, as environment variables at runtime. They are stored in Git, so everyone who can read the repository sees them.
   - `{{ url.app }}` is a placeholder. The platform fills in the full address of the running version: `https://myapp.apps.it25a.de` in production, `https://myapp-pr7.apps.it25a.de` in the preview of pull request 7. Put placeholders in quotes. More about them in [`manifest.md`](manifest.md#placeholders).
   - `secrets` lists the **names** of your GitHub secrets. Only listed secrets are passed on.
3. **Store only real secrets.** Names and settings that are not secret (database name, database user, port, URLs) belong in `environment` in `app.it25a.yml`, not in GitHub secrets. GitHub hides the value of every secret wherever it appears, also inside the address of your app. If a secret is, for example, `x-poll`, the address `https://x-poll-pr1.apps.it25a.de` is shown as `https://***-pr1.apps.it25a.de`, and GitHub then does not attach it to the deployment ("Skip setting environment url as environment 'preview' may contain secret"). The app still runs, but the link to the preview is missing in the pull request. So never use a secret value that is part of your address: the alias, `app`, `apps`, `it25a` or `pr`.
4. Your app reads each secret as an environment variable **at runtime** (Node.js: `process.env.SESSION_SECRET`; SvelteKit 3: declared in `src/env.ts` and imported from `$app/env/private`, see the [SvelteKit examples](../examples/sveltekit-sqlite/README.md); older SvelteKit: `$env/dynamic/private`).

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
- **Change the title, description, previews or who may open the app:** use the form [*Change an app*](https://github.com/IT25A/apps-registry/issues/new/choose) in `apps-registry`. A maintainer approves it. To change the address (the alias), ask a maintainer.
- **Take the app offline:** use the form [*Remove an app*](https://github.com/IT25A/apps-registry/issues/new/choose) in `apps-registry`, see [Take your app offline](#take-your-app-offline).

## Something went wrong

Every message appears in the log of the **Deploy** job (Actions tab, click the run, click the job).

| The message contains | Meaning | What to do |
|---|---|---|
| `is not registered` | There is no approved registry entry yet | Finish step 3 and wait for the merge |
| `repository ID does not match` or `is already used by` | The alias belongs to another repository, or to an app that was removed less than 30 days ago (also after deleting and recreating a repository). The message names the date | Ask a maintainer, who can release the alias earlier |
| `Only public repositories` | The repository is private | Make it public |
| `denied` / `unauthorized` while pulling | The image is still private | Step 6, point 3 |
| `Preview environments are disabled` | `previews` is `false` in the registry | Change it there, or merge to `main` |
| An error in **Plan** about `app.it25a.yml` or the Compose file | Something in your configuration is not allowed | Read the message; it names the line. Fix the file and push again |
| `unhealthy`, or `Restarting` in the container list | The app does not start, or it does not answer the route that the `HEALTHCHECK` of the Dockerfile asks (for example `/health`) | Read the log lines **below** the message: those that start with the service name (for example `api-1  \|`) are the output of your container and show the real error. If the app only lacks the route, add it (see the example's README) or remove the `HEALTHCHECK` lines. The old version keeps running meanwhile |
| `Skip setting environment url as environment 'preview' may contain secret` (in *Complete job*), or `***` inside an address | One of your GitHub secrets has a value that is part of the address, for example the alias | Do not store that value as a secret (see step 5), or choose another value, and push again |
| The **Build** stage fails | The Dockerfile or the app build is broken | Read the log of the failing step; it is the same output as `docker build` on your computer |

**You do not have to check your configuration locally.** The *Plan* stage validates `app.it25a.yml` on every push and pull request before anything is built or started, and the registry pull request has its own check.
If you use VS Code with the YAML extension by Red Hat, add this line at the top of `app.it25a.yml` for live hints while typing:
`# yaml-language-server: $schema=https://raw.githubusercontent.com/IT25A/deploy-workflows/main/schema/it25a.schema.json`

A failed **first** deployment leaves nothing behind, so you can simply fix and push again.

## Take your app offline

- **Previews** disappear by themselves when the pull request is closed or merged, or after 14 days.
- **The production app** stays online until a maintainer takes it down. Use the form [*Remove an app*](https://github.com/IT25A/apps-registry/issues/new/choose) in `apps-registry`. The maintainer asks in the issue whether your data (database, uploaded files) may be deleted: taking an app down **deletes its volumes**, so export what you want to keep first.
- When the app is down, the pull request that removes the entry from `apps-registry` is created for you. You do not need to open one.
- Then delete `.github/workflows/deploy.yml` (or the repository) so no new deployments are tried, and delete the container packages on GitHub (the organization's *Packages* page) if you do not need them.

## Apps for course members only

By default (`"production_access": "course"`, and for previews), visitors first see a short explanation, sign in, and come back to the page they wanted. Your app needs no login code. It receives two request headers:

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
| Databases | Files such as SQLite need `volumes` in `app.it25a.yml`; database servers such as `postgres` need a `compose.it25a.yml` (approved images only); the data lives in volumes on the server |

There are **no database backups yet**. Keep your own copy of data that you cannot recreate.
Apps are for course projects. Do not store personal data of third parties.

## Checklist

- [ ] Repository is in `IT25A` and public
- [ ] `Dockerfile` and `.dockerignore` are in the root
- [ ] `.github/workflows/deploy.yml` exists
- [ ] Registry pull request is merged
- [ ] Secrets are created and listed in `app.it25a.yml` (if needed)
- [ ] Image is set to public after the first build
- [ ] The address from the *Deploy* log opens

## Further reading

- [`templates/`](../templates/): Dockerfiles for common frameworks
- [`manifest.md`](manifest.md): all fields of `app.it25a.yml`, routing, placeholders, Compose variables
- [`examples/`](../examples/README.md): complete projects (React, React and Express, with PostgreSQL, SvelteKit with SQLite or PostgreSQL and login, C++)
- [`apps-registry`](https://github.com/IT25A/apps-registry): registry fields and rules

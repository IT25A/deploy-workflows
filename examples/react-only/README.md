# React (or any Vite frontend) without a server of your own

Your project is a website that is built to static files and talks to no backend of your own (or to an external API).

## Files

| File | Where | Notes |
|---|---|---|
| [`Dockerfile`](Dockerfile) | root of the repository | Builds the site with `npm run build` and serves the folder `dist` |
| [`.dockerignore`](../../templates/.dockerignore) | root of the repository | Copy it from `templates/` |

You do **not** need an `it25a.yml`: the platform starts one service on port 3000 and publishes it at `https://<alias>.apps.it25a.de`.

## Check before you push

- `npm run build` works on your computer and creates the folder `dist`. (Create React App and some other tools use `build`: change `dist` to `build` in the last two lines of the Dockerfile.)
- `package-lock.json` is committed.
- Links like `/about` work after a reload: the Dockerfile uses `serve --single`, which returns `index.html` for unknown addresses, so React Router with `BrowserRouter` works.

## Good to know

- Everything in a frontend is **public**. Never put passwords or API keys into the code or into `VITE_` variables: they end up in the files that every visitor downloads.
- Variables that start with `VITE_` are fixed when the site is built. To pass a value, add it to the Dockerfile as `ARG` (see the comment in it) and to `build.args` in an `it25a.yml`.
- You want a backend later? Continue with [`react-express/`](../react-express/).

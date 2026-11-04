# Frontend that is built to static files (React, Vue, Svelte with Vite, ...).
# Save as "Dockerfile" in the root of your repository (or in your frontend folder, see docs/manifest.md).
#
# Before you use it, check:
#   - "npm run build" works on your computer and creates the folder "dist"
#     (some tools use "build" instead: change both places below)
#   - package-lock.json is committed to Git

# Stage 1 "build": install everything and build the static files.
FROM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Only needed if the frontend talks to a separate backend: the address is baked into the files here.
# The platform fills it in through "build.args" in app.it25a.yml (see examples/react-express/README.md).
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Stage 2: a tiny web server that serves the files. "--single" makes the browser routing of
# single-page apps work (every unknown address returns index.html).
FROM node:26-alpine
WORKDIR /app
RUN npm install -g serve@14
COPY --from=build /app/dist ./dist
# Run as the unprivileged user "node" instead of root: a bug in the app then cannot change the container.
USER node
EXPOSE 3000
# Health check: Docker asks the app every 10 seconds whether it is alive. The deployment waits until
# the first check succeeds; if it never does, the update is rolled back and the old version keeps running.
# The start page answers with status 200, so no extra route is needed.
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/',{signal:AbortSignal.timeout(3000)}).then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["serve", "--single", "--listen", "3000", "dist"]

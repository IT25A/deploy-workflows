# SvelteKit app with SQLite (better-sqlite3). Save as "Dockerfile" in the root of your repository.
#
# Before you use it, check:
#   - svelte.config.js uses "@sveltejs/adapter-node" (npm install -D @sveltejs/adapter-node)
#   - "npm run build" works on your computer and creates the folder "build"
#   - package-lock.json is committed to Git
#   - ".env.example" is committed and contains a value for every variable of src/env.ts (see README.md)
#   - the database file path comes from the DATABASE_PATH variable (see README.md)

# The Debian based image ("slim") is used because better-sqlite3 is a native module and ships
# ready-made binaries for it. If the build still fails at "npm ci", add this line after FROM in the build stage:
#   RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ && rm -rf /var/lib/apt/lists/*

# Stage 1 "build": install everything, build the project, then remove the development tools again.
FROM node:26-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# SvelteKit 3 checks the variables of src/env.ts while it builds, so they need values now.
# The harmless dummy values come from .env.example; the real ones are set when the container starts.
COPY .env.example .env
RUN npm run build
RUN npm prune --omit=dev

# Stage 2: the final image only contains the built app and its runtime dependencies (no .env, no dummy values).
FROM node:26-slim
WORKDIR /app
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000
COPY --from=build /app/build ./build
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./

# The database file lives in /data. A new volume copies the owner of this folder, so the unprivileged
# user "node" can write to it. (The folder must exist before "USER node" and belong to that user.)
RUN mkdir -p /data && chown node:node /data
# Run as the unprivileged user "node" instead of root: a bug in the app then cannot change the container.
USER node
EXPOSE 3000
# Health check: Docker asks the app every 10 seconds whether it is alive. The deployment waits until
# the first check succeeds; if it never does, the update is rolled back and the old version keeps running.
# It needs a route "/health" in your app that answers with status 200 (see README.md).
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/health',{signal:AbortSignal.timeout(3000)}).then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "build"]

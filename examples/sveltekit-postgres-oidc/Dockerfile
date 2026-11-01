# SvelteKit app with a PostgreSQL database. Save as "Dockerfile" in the root of your repository.
#
# Before you use it, check:
#   - svelte.config.js uses "@sveltejs/adapter-node" (npm install -D @sveltejs/adapter-node)
#   - "npm run build" works on your computer and creates the folder "build"
#   - package-lock.json is committed to Git
#   - ".env.example" is committed and contains a value for every variable of src/env.ts (see README.md)
#   - the folders "scripts" (with migrate.js) and "migrations" exist (see README.md)
#   - "pg" is listed under "dependencies" (not "devDependencies"), because the migration script needs it

# Stage 1 "build": install everything, build the project, then remove the development tools again.
FROM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# SvelteKit 3 checks the variables of src/env.ts while it builds, so they need values now.
# The harmless dummy values come from .env.example; the real ones are set when the container starts.
COPY .env.example .env
RUN npm run build
RUN npm prune --omit=dev

# Stage 2: the final image only contains what is needed to run the app (no .env, no dummy values).
FROM node:26-alpine
WORKDIR /app
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000
COPY --from=build /app/build ./build
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./
COPY --from=build /app/scripts ./scripts
COPY --from=build /app/migrations ./migrations

# Run as the unprivileged user "node" instead of root: a bug in the app then cannot change the container.
USER node
EXPOSE 3000

# Health check: Docker asks the app every 10 seconds whether it is alive. The deployment waits until
# the first check succeeds; if it never does, the update is rolled back and the old version keeps running.
# This one only opens a connection to the port. That is enough here: the container starts the server only
# after the migrations have worked, so the database is reachable. It also works when the start page
# redirects to the login. A route that checks the database is in README.md (then use fetch on "/health").
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD node -e "require('net').connect(3000,'127.0.0.1').on('connect',()=>process.exit(0)).on('error',()=>process.exit(1))"

# First bring the database up to date, then start the server. If the migration fails, the container
# stops and the update is rolled back.
CMD ["sh", "-c", "node scripts/migrate.js && node build"]

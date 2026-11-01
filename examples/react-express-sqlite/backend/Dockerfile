# Express backend with an SQLite file (better-sqlite3). Save as "Dockerfile" in the backend folder.
#
# Before you use it, check:
#   - package.json has a "start" script (for example "start": "node index.js")
#   - package-lock.json is committed to Git
#   - "better-sqlite3" is listed under "dependencies" (not "devDependencies")
#   - your app listens on port 3000 (or on the port that the PORT variable contains)
#   - the database file path comes from the DB_PATH variable (see README.md)

FROM node:26-alpine
WORKDIR /app

# Step 1: install the dependencies (copied first so Docker can reuse this step).
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Step 2: copy the rest of your project.
COPY . .

ENV NODE_ENV=production
ENV PORT=3000

# The database file lives in /data. A new volume copies the owner of this folder, so the unprivileged
# user "node" can write to it. IMPORTANT: this line must come BEFORE "USER node", because from then on
# every command runs as "node", who is not allowed to create folders in "/".
RUN mkdir -p /data && chown node:node /data

# Run as the unprivileged user "node" instead of root: a bug in the app then cannot change the container.
USER node
EXPOSE 3000

# Health check: Docker asks the app every 10 seconds whether it is alive. The deployment waits until
# the first check succeeds; if it never does, the update is rolled back and the old version keeps running.
# It needs a route "/api/health" in your app that answers with status 200 (see README.md).
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/api/health',{signal:AbortSignal.timeout(3000)}).then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["npm", "start"]

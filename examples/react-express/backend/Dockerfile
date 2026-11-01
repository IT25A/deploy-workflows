# Plain Node.js app (Express, Fastify, Koa, ...). Save as "Dockerfile" in the folder of this service.
#
# Before you use it, check:
#   - package.json has a "start" script (for example "start": "node index.js")
#   - package-lock.json is committed to Git
#   - your app listens on port 3000 (or on the port that the PORT variable contains)

# The starting point: a small Linux with Node.js 26 already installed.
FROM node:26-alpine

# All following commands run in this folder inside the container.
WORKDIR /app

# Step 1: install the dependencies. Only the two package files are copied first, so Docker can
# reuse this step as long as your dependencies do not change (faster builds).
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Step 2: copy the rest of your project (the files listed in .dockerignore are left out).
COPY . .

ENV NODE_ENV=production
ENV PORT=3000
# Run as the unprivileged user "node" instead of root: a bug in the app then cannot change the container.
USER node
EXPOSE 3000

# Health check: Docker asks the app every 10 seconds whether it is alive. The deployment waits until
# the first check succeeds; if it never does, the update is rolled back and the old version keeps running.
# It needs a route "/api/health" in your app that answers with status 200 (see README.md).
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/api/health',{signal:AbortSignal.timeout(3000)}).then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

# Step 3: the command that starts your app.
CMD ["npm", "start"]

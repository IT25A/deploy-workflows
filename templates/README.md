# Dockerfile templates

Copy the template that fits your project to the root of your repository and rename it to exactly `Dockerfile` (capital D, no file extension).
Also copy `.dockerignore`. The comments in each file say what to check first. The step-by-step guide is [`docs/getting-started.md`](../docs/getting-started.md).

| Template | Use it for |
|---|---|
| [`Dockerfile.node`](Dockerfile.node) | Node.js backend or full app without a build step (Express, Fastify, ...) |
| [`Dockerfile.node-typescript`](Dockerfile.node-typescript) | Node.js backend with a build step (TypeScript, NestJS, ...) |
| [`Dockerfile.sveltekit`](Dockerfile.sveltekit) | SvelteKit with `adapter-node` |
| [`Dockerfile.vite-static`](Dockerfile.vite-static) | Frontend that is built to static files (React, Vue, Svelte with Vite) |
| [`Dockerfile.python-fastapi`](Dockerfile.python-fastapi) | Python with FastAPI |
| [`Dockerfile.python-flask`](Dockerfile.python-flask) | Python with Flask |

The SvelteKit template expects a `.env.example` (see the comments in the file). These templates have no health check, so that they work with any app. When you want one, copy the `HEALTHCHECK` lines and the matching route from the Dockerfiles in [`../examples/`](../examples/README.md).

Another language or framework? The rules are always the same: install the dependencies, copy the code, start the app on port `3000` on all network interfaces (`0.0.0.0`).

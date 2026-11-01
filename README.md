# deploy-workflows

Reusable deploy workflow, manifest schema and docs of the IT25A hosting platform.
Apps are deployed to `https://<alias>.apps.it25a.de`; every open pull request gets its own preview.

## Deploy your repository

New here? Read the step-by-step guide: [`docs/getting-started.md`](docs/getting-started.md).

1. Create the repository in the organization `IT25A` (a personal repository only after talking to the maintainers) and make it **public** and make sure it has a `Dockerfile` (listening on port 3000) or an [`it25a.yml`](docs/manifest.md).
2. Register it in [`IT25A/apps-registry`](https://github.com/IT25A/apps-registry) with a pull request. A maintainer merges it.
3. Copy [`examples/caller-deploy.yml`](examples/caller-deploy.yml) to `.github/workflows/deploy.yml` in your repository.
4. Create the secrets that your `it25a.yml` declares (repository secrets).
5. Push to `main`. The workflow validates the manifest, builds the images, deploys and prints the URL.

Open pull requests are deployed as `https://<alias>-pr<number>.apps.it25a.de` (course members only, unless the registry says otherwise)
and are removed when the pull request is closed, or after 14 days.

## What the workflow does

| Job | Purpose |
|---|---|
| Prepare | Finds out which version of this workflow is running, so the scripts come from the same commit |
| Plan | Validates `it25a.yml`, asks the deployer for URLs and build arguments, creates the build matrix |
| Build | One job per service: builds the image with a layer cache and pushes it to GHCR |
| Deploy | Sends the image names and the declared secrets to the deployer and shows its log |
| Remove preview | When a pull request is closed: removes the preview environment |

Pull requests from forks and from Dependabot are skipped: GitHub gives them neither secrets nor an identity token.
The deployer only accepts requests from this workflow (it checks the signed `job_workflow_ref` claim), so the steps cannot be copied into other workflows.

## Versions

Use a tag in the caller (`@v1`). Breaking changes get a new major tag (`v2`). Fixes that do not break callers move the existing `v1` tag forward.
The deployer accepts tags like `v1`, `v1.2` or `v1.2.3` and `@main`; other refs (branches, commit hashes) are rejected.

## Develop

```bash
pip install -r scripts/requirements.txt pytest
pytest
python scripts/validate_manifest.py path/to/it25a.yml
```

`scripts/it25a_ci.py` is the client that runs inside the workflow. The tests run it against a stub of the deployer.
The workflow file itself can only be tested on GitHub, with a test repository.

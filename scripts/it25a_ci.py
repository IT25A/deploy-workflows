#!/usr/bin/env python3
"""Client of the IT25A deploy workflow. Runs inside GitHub Actions.

Commands:
    plan      validate the manifest, ask the deployer for URLs and build arguments, print the build matrix
    deploy    send images and secrets to the deployer and follow the job until it is done
    cleanup   remove the preview environment of the current pull request

Only the standard library is needed for `deploy` and `cleanup`; `plan` also uses PyYAML and jsonschema.
All input comes from the environment of the workflow (see deploy.yml).
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_API_URL = "https://cd.it25a.de"
AUDIENCE = "it25a-deployer"
TOKEN_MAX_AGE = 120          # seconds; GitHub tokens live longer, but a fresh one per request is cheap
POLL_INTERVAL = 2.0
MAX_WAIT = 20 * 60           # the deployer has its own timeouts; this only stops the workflow from hanging
MAX_COMPOSE_BYTES = 256 * 1024
MAX_MANIFEST_BYTES = 64 * 1024

ZERO_CONFIG = {"services": {"app": {"build": ".", "port": 3000, "route": {"host": "@"}}}}


class CiError(Exception):
    """A problem the user can understand and fix. Shown as a workflow error."""


# ----------------------------------------------------------------------------- output helpers


def _escape(message: str) -> str:
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def annotate(level: str, message: str) -> None:
    if os.getenv("GITHUB_ACTIONS") == "true":
        print(f"::{level}::{_escape(message)}", flush=True)
    else:
        print(f"{level.upper()}: {message}", flush=True)


def set_output(name: str, value: str) -> None:
    path = os.getenv("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        if "\n" in value:
            handle.write(f"{name}<<IT25A_EOF\n{value}\nIT25A_EOF\n")
        else:
            handle.write(f"{name}={value}\n")


def write_summary(markdown: str) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(markdown + "\n")


# ----------------------------------------------------------------------------- deployer API


class Api:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._token: str | None = None
        self._fetched = 0.0

    def token(self) -> str:
        if self._token and time.time() - self._fetched < TOKEN_MAX_AGE:
            return self._token
        url, request_token = os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL"), os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
        if not url or not request_token:
            raise CiError(
                "GitHub did not provide an OIDC token. Add 'id-token: write' to the permissions "
                "of the calling workflow (see the example in deploy-workflows)."
            )
        separator = "&" if "?" in url else "?"
        request = urllib.request.Request(
            f"{url}{separator}audience={AUDIENCE}", headers={"Authorization": f"bearer {request_token}"}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                token = json.load(response)["value"]
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
            raise CiError(f"Could not request an OIDC token from GitHub: {exc}") from exc
        print(f"::add-mask::{token}", flush=True)
        self._token, self._fetched = token, time.time()
        return token

    def call(self, method: str, path: str, body: dict | None = None, *, retries: int = 0) -> tuple[int, dict]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        for attempt in range(retries + 1):
            headers = {
                "Authorization": f"Bearer {self.token()}",
                "Accept": "application/json",
                "User-Agent": "it25a-deploy-workflow",
            }
            if data is not None:
                headers["Content-Type"] = "application/json"
            request = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return response.status, _parse(response.read())
            except urllib.error.HTTPError as exc:
                if exc.code in (502, 504) and attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                return exc.code, _parse(exc.read())
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise CiError(f"Cannot reach the deployer at {self.base_url}: {exc}") from exc
        raise AssertionError("unreachable")


def _parse(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"))
        return value if isinstance(value, dict) else {"value": value}
    except ValueError:
        return {"error": raw.decode("utf-8", "replace")[:300] or "empty response"}


def check(status: int, payload: dict, action: str) -> dict:
    if status < 400:
        return payload
    lines = [f"The deployer refused to {action} (HTTP {status}): {payload.get('error', 'unknown error')}"]
    lines += [f"- {item}" for item in payload.get("errors") or []]
    if status == 401:
        lines.append("The OIDC token was not accepted. Is the workflow called from the official deploy-workflows?")
    if status == 403 and "not registered" in str(payload.get("error", "")):
        lines.append("Register the repository in IT25A/apps-registry first.")
    raise CiError("\n".join(lines))


def follow_job(api: Api, job_id: str, action: str) -> dict:
    """Print the log of a job until it is finished. Returns the final job."""
    print(f"Job {job_id}", flush=True)
    since, deadline = 0, time.time() + MAX_WAIT
    while True:
        status, job = api.call("GET", f"/v1/jobs/{job_id}?since={since}", retries=3)
        job = check(status, job, f"report the {action} job")
        for line in job.get("logs", []):
            print(line, flush=True)
        since = job.get("next", since)
        if job.get("done"):
            if job.get("status") != "succeeded":
                raise CiError(job.get("error") or f"The {action} failed. See the deployer log above.")
            return job
        if time.time() > deadline:
            raise CiError(
                f"Gave up waiting for the {action} after {MAX_WAIT // 60} minutes. "
                "It may still finish on the server."
            )
        time.sleep(POLL_INTERVAL)


# ----------------------------------------------------------------------------- commands


MANIFEST_NAMES = ("app.it25a.yml", "app.it25a.yaml")
OLD_MANIFEST_NAMES = ("it25a.yml", "it25a.yaml")


def find_manifest(root: Path) -> Path:
    """Path of the manifest: `app.it25a.yml` or `app.it25a.yaml`, but not both.

    A repository that still has the old file name gets a clear error instead of silently falling back to zero-config mode.
    """
    found = [name for name in MANIFEST_NAMES if (root / name).is_file()]
    if len(found) > 1:
        raise CiError(f"Both {found[0]} and {found[1]} exist. Keep only one of them.")
    if found:
        return root / found[0]
    old = [name for name in OLD_MANIFEST_NAMES if (root / name).is_file()]
    if old:
        raise CiError(f"The manifest was renamed: rename {old[0]} to {MANIFEST_NAMES[0]} (or {MANIFEST_NAMES[1]}).")
    return root / MANIFEST_NAMES[0]


def cmd_plan(args: argparse.Namespace) -> None:
    import yaml  # only needed here

    from validate_manifest import validate

    root = Path(args.repo_root).resolve()
    manifest_path = find_manifest(root)
    if manifest_path.is_file():
        errors, warnings = validate(manifest_path, root)
        for warning in warnings:
            annotate("warning", warning)
        if errors:
            raise CiError("app.it25a.yml is invalid:\n" + "\n".join(f"- {e}" for e in errors))
        text: str | None = manifest_path.read_text(encoding="utf-8")
        if len(text.encode("utf-8")) > MAX_MANIFEST_BYTES:
            raise CiError("app.it25a.yml is larger than 64 KiB.")
        data = yaml.safe_load(text)
    elif (root / "Dockerfile").is_file():
        print("No app.it25a.yml found: using zero-config mode (Dockerfile in the root, port 3000).")
        text, data = None, ZERO_CONFIG
    else:
        raise CiError(
            "Neither an app.it25a.yml nor a Dockerfile was found in the repository root. "
            "Add one of them (see docs/manifest.md in deploy-workflows)."
        )

    api = Api(args.api_url)
    status, payload = api.call("POST", "/v1/resolve", {"manifest": text}, retries=2)
    plan = check(status, payload, "plan this deployment")

    repository, sha = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_SHA"]
    tag = f"main-{sha[:7]}" if plan["kind"] == "production" else f"pr{plan['pr_number']}-{sha[:7]}"

    include, images = [], {}
    for service in plan["built_services"]:
        build = data["services"][service]["build"]
        if isinstance(build, str):
            context, dockerfile, target = build, "Dockerfile", ""
        else:
            context = build.get("context", ".")
            dockerfile = build.get("dockerfile", "Dockerfile")
            target = build.get("target", "")
        image = f"ghcr.io/{repository.lower()}/{service}:{tag}"
        images[service] = image
        build_args = plan.get("build_args", {}).get(service, {})
        include.append(
            {
                "service": service,
                "context": context,
                "file": posixpath.normpath(posixpath.join(context, dockerfile)),
                "target": target,
                "build_args": "\n".join(f"{key}={value}" for key, value in build_args.items()),
                "image": image,
            }
        )

    compose = data.get("compose") or ""
    set_output("matrix", json.dumps({"include": include}, separators=(",", ":")))
    set_output("has_builds", "true" if include else "false")
    set_output("images", json.dumps(images, separators=(",", ":")))
    set_output("secrets", json.dumps(plan.get("secrets", []), separators=(",", ":")))
    set_output("compose", compose)
    set_output("project", plan["project"])

    kind = "Preview" if plan["kind"] == "preview" else "Production"
    print(f"{kind} deployment '{plan['project']}' of {repository}@{sha[:7]}")
    for service, url in plan.get("urls", {}).items():
        print(f"  {service}: {url}")
    for item in include:
        print(f"  build {item['service']}: {item['context']} -> {item['image']}")


def _read_json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name, "")
    if not raw.strip():
        return default
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise CiError(f"Internal error: {name} is not valid JSON ({exc}).") from exc


def cmd_deploy(args: argparse.Namespace) -> None:
    root = Path(args.repo_root).resolve()
    images: dict[str, str] = _read_json_env("IT25A_IMAGES", {})
    declared: list[str] = _read_json_env("IT25A_SECRET_NAMES", [])
    available: dict[str, str] = _read_json_env("IT25A_SECRETS", {})

    missing = [name for name in declared if not available.get(name)]
    if missing:
        raise CiError(
            "These secrets are declared in app.it25a.yml but are empty or missing in GitHub: "
            + ", ".join(missing)
            + ". Create them under Settings > Secrets and variables > Actions (repository secrets)."
        )
    secrets = {name: available[name] for name in declared}

    manifest_path = find_manifest(root)
    manifest_text = manifest_path.read_text(encoding="utf-8") if manifest_path.is_file() else None

    compose_text = None
    compose_path = os.getenv("IT25A_COMPOSE_PATH", "")
    if compose_path:
        file = (root / compose_path).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            raise CiError(f"Compose file '{compose_path}' not found.")
        compose_text = file.read_text(encoding="utf-8")
        if len(compose_text.encode("utf-8")) > MAX_COMPOSE_BYTES:
            raise CiError("The compose file is larger than 256 KiB.")

    api = Api(args.api_url)
    status, payload = api.call(
        "POST",
        "/v1/deploy",
        {"manifest": manifest_text, "compose": compose_text, "images": images, "secrets": secrets},
    )
    submitted = check(status, payload, "start this deployment")
    follow_job(api, submitted["job_id"], "deployment")

    urls: dict[str, str] = submitted.get("urls", {})
    if urls:
        set_output("url", next(iter(urls.values())))
    set_output("project", submitted.get("project", ""))
    rows = "\n".join(f"| {service} | {url} |" for service, url in urls.items())
    write_summary(
        f"### Deployed `{submitted.get('project')}`\n\n"
        + (f"| Service | URL |\n|---|---|\n{rows}\n" if rows else "No service is reachable from outside.\n")
    )
    for service, url in urls.items():
        print(f"Live: {service} -> {url}")


def cmd_cleanup(args: argparse.Namespace) -> None:
    # After a merge, GitHub sets the ref of a closed pull request to the base branch, so the deployer
    # cannot read the number from the token. The workflow passes it explicitly.
    body: dict[str, Any] = {}
    number = os.getenv("IT25A_PR_NUMBER", "").strip()
    if number.isdigit():
        body["pr_number"] = int(number)
    api = Api(args.api_url)
    status, payload = api.call("POST", "/v1/cleanup", body)
    if status == 404:
        print(f"Nothing to clean up: {payload.get('error', 'no deployment found')}")
        return
    submitted = check(status, payload, "clean up this preview")
    follow_job(api, submitted["job_id"], "cleanup")
    write_summary(f"### Removed preview `{submitted.get('project')}`")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["plan", "deploy", "cleanup"])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--api-url", default=os.getenv("IT25A_API_URL", DEFAULT_API_URL))
    args = parser.parse_args(argv)
    try:
        {"plan": cmd_plan, "deploy": cmd_deploy, "cleanup": cmd_cleanup}[args.command](args)
    except CiError as exc:
        annotate("error", str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

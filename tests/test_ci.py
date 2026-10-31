from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

import it25a_ci
from conftest import read_outputs

ROOT = Path(__file__).resolve().parents[1]

MANIFEST = """
version: 1
services:
  web:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
      target: runtime
      args:
        PUBLIC_API_URL: "{{ url.api }}"
    route: { host: "@" }
  api:
    build: ./backend
    port: 3001
    route: { host: "@", path: /api }
    secrets: [SESSION_SECRET]
"""

RESOLVE = {
    "alias": "demo", "kind": "production", "pr_number": None, "project": "demo-main",
    "built_services": ["web", "api"],
    "urls": {"web": "https://demo.apps.it25a.de", "api": "https://demo.apps.it25a.de/api"},
    "build_args": {"web": {"PUBLIC_API_URL": "https://demo.apps.it25a.de/api"}, "api": {}},
    "secrets": ["SESSION_SECRET"],
}


def make_repo(tmp_path: Path, manifest: str | None = MANIFEST) -> Path:
    repo = tmp_path / "repo"
    (repo / "frontend").mkdir(parents=True)
    (repo / "backend").mkdir()
    (repo / "frontend" / "Dockerfile.prod").write_text("FROM scratch\n")
    (repo / "backend" / "Dockerfile").write_text("FROM scratch\n")
    if manifest is not None:
        (repo / "it25a.yml").write_text(manifest)
    return repo


def run(*argv: str) -> int:
    return it25a_ci.main(list(argv))


def test_plan_builds_matrix(stub, tmp_path):
    repo = make_repo(tmp_path)
    stub.reply("POST", "/v1/resolve", (200, RESOLVE))
    assert run("plan", "--repo-root", str(repo), "--api-url", stub.url) == 0

    out = read_outputs(tmp_path)
    include = {item["service"]: item for item in json.loads(out["matrix"])["include"]}
    assert include["web"]["context"] == "./frontend"
    assert include["web"]["file"] == "frontend/Dockerfile.prod"
    assert include["web"]["target"] == "runtime"
    assert include["web"]["build_args"] == "PUBLIC_API_URL=https://demo.apps.it25a.de/api"
    assert include["api"]["file"] == "backend/Dockerfile"
    assert include["web"]["image"] == "ghcr.io/it25a/demo/web:main-abcdef1"   # lower case, tag per commit
    assert out["has_builds"] == "true"
    assert json.loads(out["secrets"]) == ["SESSION_SECRET"]
    method, path, body, auth = stub.requests[0]
    assert path == "/v1/resolve" and body == {"manifest": MANIFEST} and auth == "Bearer oidc-token"


def test_plan_preview_tag(stub, tmp_path):
    repo = make_repo(tmp_path)
    stub.reply("POST", "/v1/resolve", (200, {**RESOLVE, "kind": "preview", "pr_number": 7, "project": "demo-pr7"}))
    run("plan", "--repo-root", str(repo), "--api-url", stub.url)
    images = json.loads(read_outputs(tmp_path)["images"])
    assert images["web"].endswith(":pr7-abcdef1")


def test_plan_zero_config(stub, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Dockerfile").write_text("FROM scratch\n")
    stub.reply("POST", "/v1/resolve", (200, {**RESOLVE, "built_services": ["app"], "build_args": {}, "secrets": []}))
    assert run("plan", "--repo-root", str(repo), "--api-url", stub.url) == 0
    assert stub.requests[0][2] == {"manifest": None}
    include = json.loads(read_outputs(tmp_path)["matrix"])["include"]
    assert include[0]["file"] == "Dockerfile" and include[0]["context"] == "."


def test_plan_without_manifest_or_dockerfile(stub, tmp_path, capsys):
    repo = tmp_path / "empty"
    repo.mkdir()
    assert run("plan", "--repo-root", str(repo), "--api-url", stub.url) == 1
    assert "Neither an it25a.yml nor a Dockerfile" in capsys.readouterr().out


def test_plan_reports_invalid_manifest_before_calling_the_deployer(stub, tmp_path, capsys):
    repo = make_repo(tmp_path, "version: 1\nservices:\n  web:\n    build: ./missing\n")
    assert run("plan", "--repo-root", str(repo), "--api-url", stub.url) == 1
    assert "folder './missing' not found" in capsys.readouterr().out
    assert stub.requests == []


def test_plan_shows_deployer_refusal(stub, tmp_path, capsys):
    repo = make_repo(tmp_path)
    stub.reply("POST", "/v1/resolve", (403, {"error": "'IT25A/demo' is not registered. Open a pull request."}))
    assert run("plan", "--repo-root", str(repo), "--api-url", stub.url) == 1
    text = capsys.readouterr().out
    assert "not registered" in text and "apps-registry" in text


def deploy_env(monkeypatch, **overrides):
    values = {
        "IT25A_IMAGES": json.dumps({"web": "ghcr.io/it25a/demo/web:main-abcdef1"}),
        "IT25A_SECRET_NAMES": json.dumps(["SESSION_SECRET"]),
        "IT25A_SECRETS": json.dumps({"SESSION_SECRET": "s3cret", "OTHER": "must-not-be-sent", "github_token": "t"}),
        "IT25A_COMPOSE_PATH": "",
    }
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_deploy_sends_only_declared_secrets_and_follows_job(stub, tmp_path, monkeypatch, capsys):
    repo = make_repo(tmp_path)
    deploy_env(monkeypatch)
    stub.reply("POST", "/v1/deploy", (202, {"job_id": "j1", "project": "demo-main", "urls": RESOLVE["urls"]}))
    stub.reply(
        "GET", "/v1/jobs/j1",
        (200, {"status": "running", "done": False, "logs": ["line 1"], "next": 1}),
        (200, {"status": "succeeded", "done": True, "logs": ["line 2", "finished"], "next": 3}),
    )
    assert run("deploy", "--repo-root", str(repo), "--api-url", stub.url) == 0

    body = stub.requests[0][2]
    assert body["secrets"] == {"SESSION_SECRET": "s3cret"}
    assert body["manifest"] == MANIFEST and body["compose"] is None
    assert body["images"] == {"web": "ghcr.io/it25a/demo/web:main-abcdef1"}
    text = capsys.readouterr().out
    assert "line 1" in text and "finished" in text and "Live: web -> https://demo.apps.it25a.de" in text
    assert read_outputs(tmp_path)["url"] == "https://demo.apps.it25a.de"
    assert "demo-main" in (tmp_path / "summary").read_text()
    # second poll continues after the first batch of lines
    assert stub.requests[2][1].endswith("since=1")


def test_deploy_fails_when_the_job_fails(stub, tmp_path, monkeypatch, capsys):
    repo = make_repo(tmp_path)
    deploy_env(monkeypatch)
    stub.reply("POST", "/v1/deploy", (202, {"job_id": "j1", "project": "demo-main", "urls": {}}))
    stub.reply("GET", "/v1/jobs/j1", (200, {
        "status": "failed", "done": True, "logs": ["container exited"], "next": 1, "error": "web is unhealthy"}))
    assert run("deploy", "--repo-root", str(repo), "--api-url", stub.url) == 1
    text = capsys.readouterr().out
    assert "container exited" in text and "web is unhealthy" in text


def test_deploy_reports_missing_secret_without_calling_the_deployer(stub, tmp_path, monkeypatch, capsys):
    repo = make_repo(tmp_path)
    deploy_env(monkeypatch, IT25A_SECRETS=json.dumps({"SESSION_SECRET": ""}))
    assert run("deploy", "--repo-root", str(repo), "--api-url", stub.url) == 1
    assert "SESSION_SECRET" in capsys.readouterr().out
    assert stub.requests == []


def test_deploy_shows_validation_errors(stub, tmp_path, monkeypatch, capsys):
    repo = make_repo(tmp_path)
    deploy_env(monkeypatch)
    stub.reply("POST", "/v1/deploy", (422, {"error": "x", "errors": ["images/web: wrong registry"]}))
    assert run("deploy", "--repo-root", str(repo), "--api-url", stub.url) == 1
    assert "images/web: wrong registry" in capsys.readouterr().out


def test_deploy_sends_compose_file(stub, tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    (repo / "docker-compose.yml").write_text("services: {}\n")
    deploy_env(monkeypatch, IT25A_COMPOSE_PATH="docker-compose.yml")
    stub.reply("POST", "/v1/deploy", (202, {"job_id": "j", "project": "p", "urls": {}}))
    stub.reply("GET", "/v1/jobs/j", (200, {"status": "succeeded", "done": True, "logs": [], "next": 0}))
    assert run("deploy", "--repo-root", str(repo), "--api-url", stub.url) == 0
    assert stub.requests[0][2]["compose"] == "services: {}\n"


def test_cleanup(stub, monkeypatch):
    stub.reply("POST", "/v1/cleanup", (202, {"job_id": "c1", "project": "demo-pr7"}))
    stub.reply("GET", "/v1/jobs/c1", (200, {"status": "succeeded", "done": True, "logs": ["Removed"], "next": 1}))
    assert run("cleanup", "--api-url", stub.url) == 0


def test_cleanup_tolerates_unknown_preview(stub):
    stub.reply("POST", "/v1/cleanup", (404, {"error": "Nothing is deployed for this repository."}))
    assert run("cleanup", "--api-url", stub.url) == 0


def test_missing_oidc_permission(monkeypatch, capsys):
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_URL", raising=False)
    assert run("cleanup", "--api-url", "http://127.0.0.1:9") == 1
    assert "id-token: write" in capsys.readouterr().out


# ---------------------------------------------------------------- static checks of the repository files


def test_examples_match_the_schema():
    schema = json.loads((ROOT / "schema" / "it25a.schema.json").read_text())
    validator = Draft202012Validator(schema)
    for path in sorted((ROOT / "examples").glob("0*.yml")):
        errors = [e.message for e in validator.iter_errors(yaml.safe_load(path.read_text()))]
        assert not errors, (path.name, errors)


def test_workflow_structure():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "deploy.yml").read_text())
    assert "workflow_call" in workflow[True]            # PyYAML reads the key `on` as True
    jobs = workflow["jobs"]
    assert set(jobs) == {"meta", "plan", "build", "deploy", "cleanup"}
    for name in ("meta", "plan", "deploy", "cleanup"):
        assert jobs[name]["permissions"]["id-token"] == "write"
    assert jobs["build"]["permissions"] == {"contents": "read", "packages": "write"}
    assert "id-token" not in jobs["build"]["permissions"]   # image builds never see the OIDC token
    assert "type=gha" in jobs["build"]["steps"][-1]["with"]["cache-from"]
    # the caller must grant everything the reusable workflow asks for
    caller = yaml.safe_load((ROOT / "examples" / "caller-deploy.yml").read_text())
    granted = caller["permissions"]
    for job in jobs.values():
        for permission, level in job["permissions"].items():
            assert granted.get(permission) == level or (level == "read" and granted.get(permission) == "write")

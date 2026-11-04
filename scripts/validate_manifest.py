#!/usr/bin/env python3
"""Validate an app.it25a.yml: JSON schema plus additional rules (paths, routing, placeholders).

Usage:
    python scripts/validate_manifest.py app.it25a.yml [--repo-root .]

The validate() function is also used by the deploy workflow and by the deployer.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "schema" / "it25a.schema.json"
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_]+)(?:\.([A-Za-z0-9-]+))?\s*\}\}")
REF_KINDS = {"url", "host"}  # need a service as target, e.g. {{ url.api }}
PLAIN_KINDS = {"alias"}      # take no target: {{ alias }}

RESERVED_MOUNT_ROOTS = {"proc", "sys", "dev"}


def mount_errors(entries: list[str], where: str) -> list[str]:
    """Rules for `volumes: ["name:/folder"]` that the schema cannot express."""
    errors: list[str] = []
    names: set[str] = set()
    targets: set[str] = set()
    for entry in entries:
        name, _, target = entry.partition(":")
        parts = target.split("/")[1:]
        if target == "/":
            errors.append(f"{where}: '{entry}' mounts the root folder.")
        elif any(part in ("", ".", "..") for part in parts):
            errors.append(f"{where}: '{target}' is not a valid folder (no '.', '..', double or trailing slash).")
        elif parts[0] in RESERVED_MOUNT_ROOTS:
            errors.append(f"{where}: '{target}' is a system folder.")
        if name in names:
            errors.append(f"{where}: volume '{name}' is used twice.")
        if target in targets:
            errors.append(f"{where}: folder '{target}' is used twice.")
        names.add(name)
        targets.add(target)
    return errors


def validate(manifest_path: Path, repo_root: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [f"{manifest_path.name} not readable: {exc}"], warnings
    if not isinstance(data, dict):
        return ["The file must contain a YAML object."], warnings

    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(data), key=lambda e: [str(p) for p in e.absolute_path]):
        where = "/".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"{where}: {err.message}")
    if errors:
        return errors, warnings

    root = repo_root.resolve()
    services: dict = data["services"]

    def inside(relative: str) -> Path | None:
        path = (root / relative).resolve()
        return path if path.is_relative_to(root) else None

    # Compose file
    compose = data.get("compose")
    if compose:
        compose_path = inside(compose)
        if compose_path is None or not compose_path.is_file():
            errors.append(f"compose: file '{compose}' not found.")

    # Build contexts and Dockerfiles
    for name, svc in services.items():
        build = svc.get("build")
        if build is None:
            continue
        if isinstance(build, str):
            context, dockerfile = build, "Dockerfile"
        else:
            context, dockerfile = build.get("context", "."), build.get("dockerfile", "Dockerfile")
        context_path = inside(context)
        if context_path is None or not context_path.is_dir():
            errors.append(f"services/{name}/build: folder '{context}' not found.")
            continue
        dockerfile_path = (context_path / dockerfile).resolve()
        if not dockerfile_path.is_relative_to(root) or not dockerfile_path.is_file():
            errors.append(f"services/{name}/build: Dockerfile '{dockerfile}' not found in '{context}'.")

    # Routing: at most one catch-all per host, paths must be unique
    hosts: dict[str, list[tuple[str | None, str]]] = {}
    for name, svc in services.items():
        route = svc.get("route")
        if route:
            hosts.setdefault(route["host"], []).append((route.get("path"), name))

    for host, entries in hosts.items():
        label = "main domain (@)" if host == "@" else f"host '{host}'"
        catch_all = [name for path, name in entries if path is None]
        if len(catch_all) > 1:
            errors.append(
                f"{label}: multiple services without a path ({', '.join(catch_all)}). "
                "Only one may accept all remaining requests."
            )
        seen: dict[str, str] = {}
        for path, name in entries:
            if path is None:
                continue
            if path in seen:
                errors.append(f"{label}: path '{path}' is used by '{seen[path]}' and '{name}'.")
            seen[path] = name
        if not catch_all:
            warnings.append(f"{label}: no service without a path. Requests outside the listed paths will fail.")

    if not hosts:
        warnings.append("No service has a 'route'. The app would not be reachable from outside.")

    # Volumes
    for name, svc in services.items():
        errors.extend(mount_errors(svc.get("volumes") or [], f"services/{name}/volumes"))

    # Placeholders in environment and build.args
    def check_placeholders(value: str, where: str) -> None:
        for kind, ref in PLACEHOLDER.findall(value):
            if kind in PLAIN_KINDS:
                if ref:
                    errors.append(f"{where}: '{{{{ {kind} }}}}' does not take a target.")
            elif kind in REF_KINDS:
                if not ref:
                    errors.append(f"{where}: '{{{{ {kind}.<service> }}}}' needs a service.")
                elif ref not in services:
                    errors.append(f"{where}: service '{ref}' in '{{{{ {kind}.{ref} }}}}' does not exist.")
                elif not services[ref].get("route"):
                    errors.append(f"{where}: service '{ref}' has no 'route', so there is no URL.")
            else:
                errors.append(f"{where}: unknown placeholder '{kind}'. Allowed: url, host, alias.")
        if "{{" in PLACEHOLDER.sub("", value):
            errors.append(f"{where}: invalid placeholder in '{value}'.")

    for name, svc in services.items():
        for key, value in (svc.get("environment") or {}).items():
            check_placeholders(value, f"services/{name}/environment/{key}")
        build = svc.get("build")
        if isinstance(build, dict):
            for key, value in (build.get("args") or {}).items():
                check_placeholders(value, f"services/{name}/build/args/{key}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path, nargs="?", default=Path("app.it25a.yml"))
    parser.add_argument("--repo-root", type=Path, default=None, help="default: folder of the manifest file")
    args = parser.parse_args()

    root = args.repo_root or args.manifest.parent
    errors, warnings = validate(args.manifest, root)

    in_actions = os.getenv("GITHUB_ACTIONS") == "true"
    for level, messages in (("error", errors), ("warning", warnings)):
        for message in messages:
            if in_actions:
                print(f"::{level} file={args.manifest.name}::{message}")
            else:
                print(f"{level.upper()}: {message}")

    print(f"{args.manifest.name}: {len(errors)} error(s), {len(warnings)} warning(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

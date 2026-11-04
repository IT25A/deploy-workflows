"""Every example project must pass the same validation that the deploy workflow runs."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_manifest import validate  # noqa: E402

EXAMPLES = sorted(path.parent for path in (ROOT / "examples").glob("*/app.it25a.yml"))


def test_examples_exist():
    assert len(EXAMPLES) >= 4


@pytest.mark.parametrize("folder", EXAMPLES, ids=lambda p: p.name)
def test_example_manifest_is_valid(folder):
    errors, _warnings = validate(folder / "app.it25a.yml", folder)
    assert errors == []


@pytest.mark.parametrize("folder", sorted(p for p in (ROOT / "examples").iterdir() if p.is_dir()), ids=lambda p: p.name)
def test_example_has_the_files_it_documents(folder):
    assert (folder / "README.md").is_file()
    dockerfiles = list(folder.rglob("Dockerfile"))
    assert dockerfiles, "every example needs at least one Dockerfile"


def test_relative_links_in_the_documentation_resolve():
    import re
    link = re.compile(r"\]\(([^)\s]+)\)")
    for md in ROOT.rglob("*.md"):
        if ".git" in md.parts:
            continue
        for target in link.findall(md.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path = (md.parent / target.split("#")[0]).resolve()
            assert path.exists(), f"{md.relative_to(ROOT)}: broken link {target}"


@pytest.mark.parametrize("entries, fragment", [
    (["data:/"], "root folder"),
    (["data:/data/"], "not a valid folder"),
    (["data:/a/../b"], "not a valid folder"),
    (["data:/proc/x"], "system folder"),
    (["data:/data", "data:/other"], "used twice"),
    (["one:/data", "two:/data"], "used twice"),
])
def test_volume_rules_the_schema_cannot_express(tmp_path, entries, fragment):
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    manifest = tmp_path / "app.it25a.yml"
    manifest.write_text("version: 1\nservices:\n  app:\n    build: .\n    route: { host: '@' }\n    volumes: " + str(entries) + "\n")
    errors, _warnings = validate(manifest, tmp_path)
    assert any(fragment in error for error in errors), errors


@pytest.mark.parametrize("entry", ["/host:/data", "data", "data:data", "a:/1b c"])
def test_volume_entries_must_look_like_name_and_folder(tmp_path, entry):
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    manifest = tmp_path / "app.it25a.yml"
    manifest.write_text(f"version: 1\nservices:\n  app:\n    build: .\n    route: {{ host: '@' }}\n    volumes: ['{entry}']\n")
    errors, _warnings = validate(manifest, tmp_path)
    assert errors


def test_valid_volumes_pass(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    manifest = tmp_path / "app.it25a.yml"
    manifest.write_text("version: 1\nservices:\n  app:\n    build: .\n    route: { host: '@' }\n    volumes: ['data:/data', 'logs:/var/log/app']\n")
    assert validate(manifest, tmp_path)[0] == []

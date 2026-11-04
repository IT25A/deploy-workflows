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

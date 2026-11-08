"""Build dist/deal_finder.zip (used by HACS releases and for manual installation).

Usage:
    python scripts/build.py [--version 0.1.0] [--repo user/HADealFinder]

The zip contains the *contents* of custom_components/deal_finder at its root,
which is what HACS expects for "zip_release". For a manual install, unzip it
into <config>/custom_components/deal_finder/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "custom_components" / "deal_finder"
DIST = ROOT / "dist"
PLACEHOLDER = "YOUR_GITHUB_USER/HADealFinder"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="version to write into manifest.json (e.g. 0.1.0 or v0.1.0)")
    parser.add_argument("--repo", help="GitHub repo 'user/name' replacing the placeholder in manifest.json")
    args = parser.parse_args()

    manifest = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
    if args.version:
        manifest["version"] = args.version.removeprefix("v")
    if args.repo:
        user = args.repo.split("/")[0]
        for key in ("documentation", "issue_tracker"):
            manifest[key] = manifest[key].replace(PLACEHOLDER, args.repo)
        manifest["codeowners"] = [f"@{user}"]

    DIST.mkdir(exist_ok=True)
    target = DIST / "deal_finder.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SRC.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
                continue
            rel = path.relative_to(SRC).as_posix()
            if rel == "manifest.json":
                zf.writestr(rel, json.dumps(manifest, indent=2) + "\n")
            else:
                zf.write(path, rel)
    print(f"Built {target} (version {manifest['version']}, {len(zipfile.ZipFile(target).namelist())} files)")


if __name__ == "__main__":
    main()

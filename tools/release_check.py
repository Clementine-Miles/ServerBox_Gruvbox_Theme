#!/usr/bin/env python3
"""Validate, pack and plan a release with the pinned official ServerBox tools."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen

from audit import ROOT, listings


REV = "fa7941a0b3d4dda154cbf85b007dc6348812e679"
BASE = f"https://raw.githubusercontent.com/lollipopkit/flutter_server_box/{REV}/"
SCRIPTS = Path(".claude/skills/serverbox-theme/scripts")
SCHEMA = Path("docs/schemas/fsbt-manifest.schema.json")
PINNED = {
    SCHEMA: "174e1d7bff0b825ddd00d79fe95f7abfc8f5685e",
    SCRIPTS / "validate.py": "b42ccb538b0413b715c65736469d5e5eb52ddce3",
    SCRIPTS / "pack.py": "506aae37fb31a72eea2e7f274ae184c54987f352",
    SCRIPTS / "publish.py": "90304933004aff0ec5562e72cae00926d21f77fa",
}


def retrieve(target, checkout):
    for source, expected in PINNED.items():
        if checkout:
            data = (checkout / source).read_bytes()
        else:
            with urlopen(BASE + source.as_posix(), timeout=30) as response:
                data = response.read()
        actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if actual != expected:
            raise RuntimeError(f"Unexpected upstream bytes: {source}")
        path = target / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def run(*args, cwd=ROOT):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def verify_public_assets():
    for theme_id, releases in listings(require_versions=True).items():
        for release in releases:
            expected_size = release["size"]
            with urlopen(release["url"], timeout=60) as response:
                data = response.read(expected_size + 1)
            actual = hashlib.sha256(data).hexdigest()
            if len(data) != expected_size or actual != release["sha256"]:
                raise RuntimeError(f"{theme_id} {release['version']}: published asset differs from its listing")
            print(f"{theme_id} {release['version']}: public asset verified ({len(data)} B, {actual})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serverbox", type=Path, help="checkout with the exact pinned tools and schema")
    parser.add_argument("--preview-dir", type=Path, default=ROOT.parent / "previews")
    parser.add_argument("--skip-dry-run", action="store_true", help="validate and package before a GitHub origin exists")
    parser.add_argument("--verify-public-assets", action="store_true", help="verify existing releases against their listings")
    args = parser.parse_args()
    out = args.preview_dir.resolve()
    if out == ROOT or ROOT in out.parents:
        parser.error("keep the preview directory outside the repository")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        parser.error("use an empty or new preview directory")

    checker = shutil.which("check-jsonschema")
    if not checker:
        parser.error("install check-jsonschema on PATH; full schema validation is mandatory")
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        parser.error("install jsonschema in the Python environment running this script")

    run(sys.executable, ROOT / "tools/generate.py", "--check")
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="serverbox-theme-") as directory:
        upstream = Path(directory)
        retrieve(upstream, args.serverbox)
        schema = upstream / SCHEMA
        scripts = upstream / SCRIPTS
        for folder in sorted((ROOT / "themes").glob("*/")):
            run(checker, "--schemafile", schema, folder / "manifest.toml", cwd=upstream)
            run(sys.executable, scripts / "validate.py", folder, "--schema", schema, cwd=upstream)
            target = out / (folder.name + "-preview.fsbt")
            repeat = upstream / target.name
            for package in (target, repeat):
                run(sys.executable, scripts / "pack.py", folder, "-o", package, cwd=upstream)
            if repeat.read_bytes() != target.read_bytes():
                raise RuntimeError(f"{folder.name}: packaging was not reproducible")
        run(sys.executable, ROOT / "tools/audit.py", "--schema", schema,
            "--packages", out, "--json", out / "audit.json")
        if not args.skip_dry_run:
            run(sys.executable, scripts / "publish.py", "--root", ROOT, "--dry-run", cwd=upstream)
    if args.verify_public_assets:
        verify_public_assets()


if __name__ == "__main__":
    main()

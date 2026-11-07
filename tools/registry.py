#!/usr/bin/env python3
"""Maintain the Gufo extension registry. Python standard library and Git only.

  registry.py check              validate every entry and the generated index
  registry.py index              regenerate index.json from extensions/
  registry.py verify NAME [VER]  fetch a release and compare it with its entry
  registry.py digest DIR         print the source digest gufo computes for DIR
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "extensions"
INDEX = ROOT / "index.json"
SCHEMA = 1

NAME = re.compile(r"^[a-z][a-z0-9_]*$")
VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
API = re.compile(r"^>= (0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
HANDLE = re.compile(r"^@[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
SOURCE = re.compile(r"^https://[^\s@]+$")
PLATFORMS = {"linux", "windows"}
FIELDS = {"schema", "name", "description", "homepage", "license", "maintainers",
          "source", "releases"}
RELEASE_FIELDS = {"version", "revision", "digest", "api_version", "platforms",
                  "notes"}


def tree_digest(root: Path) -> str:
    """The digest `gufo extension install` records: SHA-256 over every regular
    file below `root` outside .git, in path-component order, each as its
    relative POSIX path, a NUL byte, then its contents."""
    files = []
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = [d for d in subdirectories
                             if not (Path(directory) == root and d == ".git")]
        for name in names:
            path = Path(directory) / name
            if path.is_file():
                files.append(path.relative_to(root))
    hasher = hashlib.sha256()
    for relative in sorted(files, key=lambda p: p.parts):
        hasher.update(relative.as_posix().encode() + b"\0")
        hasher.update((root / relative).read_bytes())
    return "sha256:" + hasher.hexdigest()


def version_key(version):
    return tuple(int(part) for part in version.split("."))


def load(path: Path):
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise SystemExit(f"{path}: invalid JSON: {error}")


def validate(path: Path, entry, errors, warnings):
    def fail(message):
        errors.append(f"{path.relative_to(ROOT)}: {message}")

    if not isinstance(entry, dict):
        return fail("an entry is a JSON object")
    unknown = set(entry) - FIELDS
    missing = FIELDS - set(entry)
    if unknown:
        fail(f"unknown fields {sorted(unknown)}")
    if missing:
        return fail(f"missing fields {sorted(missing)}")
    if entry["schema"] != SCHEMA:
        fail(f"schema must be {SCHEMA}")
    name = entry["name"]
    if not isinstance(name, str) or not NAME.match(name):
        fail("name must match ^[a-z][a-z0-9_]*$")
    elif path.name != f"{name}.json":
        fail(f"file must be named {name}.json")
    for field in ("description", "homepage", "license"):
        if not isinstance(entry[field], str) or not entry[field].strip():
            fail(f"{field} must be a non-empty string")
    if entry["license"] == "NOASSERTION":
        warnings.append(f"{path.relative_to(ROOT)}: the source has no license; "
                        "review requires one before merging")
    if not isinstance(entry["source"], str) or not SOURCE.match(entry["source"]):
        fail("source must be an https Git URL without a revision")
    maintainers = entry["maintainers"]
    if (not isinstance(maintainers, list) or not maintainers
            or not all(isinstance(m, str) and HANDLE.match(m) for m in maintainers)):
        fail("maintainers must list GitHub handles such as @octocat")
    releases = entry["releases"]
    if not isinstance(releases, list) or not releases:
        return fail("releases must list at least one release")
    versions = []
    for index, release in enumerate(releases):
        where = f"releases[{index}]"
        if not isinstance(release, dict):
            fail(f"{where} must be an object")
            continue
        unknown = set(release) - RELEASE_FIELDS
        missing = (RELEASE_FIELDS - {"notes"}) - set(release)
        if unknown:
            fail(f"{where}: unknown fields {sorted(unknown)}")
        if missing:
            fail(f"{where}: missing fields {sorted(missing)}")
            continue
        if not isinstance(release["version"], str) or not VERSION.match(release["version"]):
            fail(f"{where}: version must be MAJOR.MINOR.PATCH")
            continue
        versions.append(release["version"])
        if not isinstance(release["revision"], str) or not REVISION.match(release["revision"]):
            fail(f"{where}: revision must be a full 40-character commit")
        if not isinstance(release["digest"], str) or not DIGEST.match(release["digest"]):
            fail(f"{where}: digest must be sha256:<64 hex>")
        if not isinstance(release["api_version"], str) or not API.match(release["api_version"]):
            fail(f"{where}: api_version must read '>= MAJOR.MINOR.REVISION'")
        platforms = release["platforms"]
        if (not isinstance(platforms, list) or not platforms
                or not set(platforms) <= PLATFORMS or len(set(platforms)) != len(platforms)):
            fail(f"{where}: platforms must be distinct values of {sorted(PLATFORMS)}")
        if "notes" in release and not isinstance(release["notes"], str):
            fail(f"{where}: notes must be a string")
    if len(set(versions)) != len(versions):
        fail("release versions must be unique")
    if versions != sorted(versions, key=version_key, reverse=True):
        fail("releases must be listed newest first")


def entries():
    return sorted(ENTRIES.glob("*.json"))


def build_index():
    extensions = {}
    for path in entries():
        entry = load(path)
        extensions[entry["name"]] = {
            key: entry[key] for key in ("description", "homepage", "license",
                                        "maintainers", "source", "releases")}
    return {"schema": SCHEMA, "extensions": extensions}


def render(index):
    return json.dumps(index, indent=2, sort_keys=True) + "\n"


def check():
    errors, warnings = [], []
    for path in entries():
        validate(path, load(path), errors, warnings)
    if not errors:
        expected = render(build_index())
        if not INDEX.exists() or INDEX.read_text() != expected:
            errors.append("index.json is stale: run tools/registry.py index")
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    if errors:
        return 1
    print(f"PASS: {len(entries())} extension entries and index.json")
    return 0


def fetch(source, revision, destination: Path):
    git = ["git", "-c", "advice.detachedHead=false"]
    subprocess.run(git + ["init", "--quiet", str(destination)], check=True)
    subprocess.run(git + ["-C", str(destination), "fetch", "--quiet", "--depth", "1",
                          source, revision], check=True)
    subprocess.run(git + ["-C", str(destination), "checkout", "--quiet", "FETCH_HEAD"],
                   check=True)
    head = subprocess.run(git + ["-C", str(destination), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()
    if head != revision:
        raise SystemExit(f"fetched {head}, expected {revision}")


def verify(name, version=None):
    path = ENTRIES / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"no entry {path.relative_to(ROOT)}")
    entry = load(path)
    releases = [r for r in entry["releases"] if version in (None, r["version"])]
    if not releases:
        raise SystemExit(f"{name} has no release {version}")
    failures = 0
    for release in releases:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            fetch(entry["source"], release["revision"], source)
            manifest = load(source / "extension.json")
            problems = []
            for field, expected in (("name", entry["name"]),
                                    ("version", release["version"]),
                                    ("api_version", release["api_version"]),
                                    ("platforms", release["platforms"])):
                if manifest.get(field) != expected:
                    problems.append(f"extension.json {field} is {manifest.get(field)!r}, "
                                    f"the entry says {expected!r}")
            digest = tree_digest(source)
            if digest != release["digest"]:
                problems.append(f"digest is {digest}, the entry says {release['digest']}")
            if problems:
                failures += 1
                for problem in problems:
                    print(f"error: {name} {release['version']}: {problem}")
            else:
                print(f"PASS: {name} {release['version']} at {release['revision']}")
    return 1 if failures else 0


def main(argv):
    if len(argv) >= 2 and argv[1] == "check" and len(argv) == 2:
        return check()
    if len(argv) == 2 and argv[1] == "index":
        INDEX.write_text(render(build_index()))
        return 0
    if len(argv) in (3, 4) and argv[1] == "verify":
        return verify(*argv[2:])
    if len(argv) == 3 and argv[1] == "digest":
        print(tree_digest(Path(argv[2]).resolve()))
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

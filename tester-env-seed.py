#!/usr/bin/env python3
"""Seed and verify the deterministic NoteDiscovery fixture through its API."""
import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "tester-env-seed"
EXPECTED = {
    "Projects/Atlas-Launch.md": ["#atlas", "#launch", "Maya Chen"],
    "Operations/Release-Checklist.md": ["#operations", "#release", "Atlas workspace"],
    "Research/Search-Notes.md": ["#research", "blue lantern"],
    "Welcome.md": ["#welcome", "Atlas Workspace"],
}


def request(url, method="GET", body=None):
    headers = {"Content-Type": "application/json"} if body is not None else {}
    with urlopen(Request(url, data=body, headers=headers, method=method), timeout=15) as response:
        return response.read().decode()


def seed(base):
    for path in sorted(EXPECTED):
        content = (FIXTURES / path).read_text(encoding="utf-8")
        request(
            f"{base}/api/notes/{quote(path, safe='/')}",
            "POST",
            json.dumps({"content": content}).encode(),
        )
    print(f"==> seeded {len(EXPECTED)} Markdown notes")


def verify(base):
    health = json.loads(request(f"{base}/health"))
    assert health["status"] == "healthy", health
    notes = json.loads(request(f"{base}/api/notes"))["notes"]
    actual = {note["path"] for note in notes}
    assert set(EXPECTED) <= actual, actual
    for path, markers in EXPECTED.items():
        note = json.loads(request(f"{base}/api/notes/{quote(path, safe='/')}"))
        assert all(marker in note["content"] for marker in markers), path
    print(f"==> verified healthy API and {len(EXPECTED)} seeded Markdown notes")


parser = argparse.ArgumentParser()
parser.add_argument("command", choices=("seed", "verify"))
parser.add_argument("--url", required=True)
args = parser.parse_args()
try:
    {"seed": seed, "verify": verify}[args.command](args.url.rstrip("/"))
except (AssertionError, HTTPError, OSError, ValueError) as error:
    print(f"tester-env {args.command} failed: {error}", file=sys.stderr)
    sys.exit(1)

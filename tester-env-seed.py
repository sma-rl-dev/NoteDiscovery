#!/usr/bin/env python3
"""Seed and verify the deterministic NoteDiscovery fixture through its API.

Markdown notes are written through POST /api/notes/{path}. Binary media
fixtures (checked in under tester-env-media/) are uploaded through
POST /api/upload-media and then moved with POST /api/media/move to fixed
vault paths, so re-running seed converges on identical bytes at identical
paths even though the upload endpoint stamps a timestamp on first receipt.
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "tester-env-seed"
MEDIA_SOURCES = ROOT / "tester-env-media"
EXPECTED = {
    "Projects/Atlas-Launch.md": [
        "#atlas",
        "#launch",
        "Maya Chen",
        "[Release Checklist](../Operations/Release-Checklist.md)",
        "[release notes draft](../Operations/Release%20Notes%20Draft.md)",
        "- [ ] example task written as source text",
        "> [!TIP]",
        "![[pixel.png]]",
        "![[release-onepager.pdf]]",
    ],
    "Operations/Release-Checklist.md": [
        "#operations",
        "#release",
        "Atlas workspace",
        "- [ ] 1. pack the demo kit",
    ],
    "Operations/Release Notes Draft.md": ["#release", "Atlas 0.32"],
    "Research/Search-Notes.md": [
        "#research",
        "blue lantern",
        "- lantern glow levels",
        "| lant ",
    ],
    "Welcome.md": ["#welcome", "Atlas Workspace"],
}
# Vault path -> (fixture file, MIME type). Attachments live in the
# note-folder _attachments dir (hidden from the sidebar) and resolve in the
# preview by filename with extension (case-insensitive media lookup).
MEDIA = {
    "Projects/_attachments/pixel.png": ("pixel.png", "image/png"),
    "Projects/_attachments/release-onepager.pdf": (
        "release-onepager.pdf",
        "application/pdf",
    ),
}
# Note used as the upload anchor so media lands in Projects/_attachments.
MEDIA_ANCHOR_NOTE = "Projects/Atlas-Launch.md"


def request(url, method="GET", body=None):
    headers = {"Content-Type": "application/json"} if body is not None else {}
    with urlopen(Request(url, data=body, headers=headers, method=method), timeout=15) as response:
        return response.read().decode()


def read_bytes(url):
    """Return (status, body) for a GET; 404 yields (404, b'')."""
    try:
        with urlopen(Request(url, method="GET"), timeout=15) as response:
            return response.status, response.read()
    except HTTPError as error:
        if error.code == 404:
            return 404, b""
        raise


def post_multipart(url, fields, filename, content_type, data):
    boundary = "----testerenvseedboundary"
    body = bytearray()
    for name, value in fields.items():
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="{name}"\r\n\r\n{value}\r\n'
        ).encode()
    body += (
        f"--{boundary}\r\nContent-Disposition: form-data; "
        f'name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode()
    body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    with urlopen(Request(url, data=bytes(body), headers=headers, method="POST"), timeout=30) as response:
        return response.read().decode()


def put_note(base, path):
    content = (FIXTURES / path).read_text(encoding="utf-8")
    request(
        f"{base}/api/notes/{quote(path, safe='/')}",
        "POST",
        json.dumps({"content": content}).encode(),
    )


def ensure_media(base, target):
    fixture_name, content_type = MEDIA[target]
    wanted = (MEDIA_SOURCES / fixture_name).read_bytes()
    status, body = read_bytes(f"{base}/api/media/{quote(target, safe='/')}")
    if status == 200 and body == wanted:
        return "present"
    if status != 404 and body != wanted:
        raise AssertionError(f"unexpected bytes at {target}")
    uploaded = json.loads(
        post_multipart(
            f"{base}/api/upload-media",
            {"note_path": MEDIA_ANCHOR_NOTE},
            fixture_name,
            content_type,
            wanted,
        )
    )["path"]
    if uploaded != target:
        try:
            request(
                f"{base}/api/media/move",
                "POST",
                json.dumps({"oldPath": uploaded, "newPath": target}).encode(),
            )
        except HTTPError as error:
            # Another seed run already moved an identical upload here.
            if error.code != 409:
                raise
    status, body = read_bytes(f"{base}/api/media/{quote(target, safe='/')}")
    assert status == 200 and body == wanted, target
    return "seeded"


def seed(base):
    for path in sorted(EXPECTED):
        put_note(base, path)
    results = {}
    for target in sorted(MEDIA):
        results[target] = ensure_media(base, target)
    # Re-save the embedding note after media exists so the link index sees
    # the embeds against present files; content is byte-identical.
    put_note(base, MEDIA_ANCHOR_NOTE)
    print(f"==> seeded {len(EXPECTED)} Markdown notes and {len(MEDIA)} media files {results}")


def verify(base):
    health = json.loads(request(f"{base}/health"))
    assert health["status"] == "healthy", health
    notes = json.loads(request(f"{base}/api/notes"))["notes"]
    actual = {note["path"] for note in notes}
    assert set(EXPECTED) <= actual, actual
    for path, markers in EXPECTED.items():
        note = json.loads(request(f"{base}/api/notes/{quote(path, safe='/')}"))
        assert all(marker in note["content"] for marker in markers), path
    for target in sorted(MEDIA):
        fixture_name, _ = MEDIA[target]
        wanted = (MEDIA_SOURCES / fixture_name).read_bytes()
        status, body = read_bytes(f"{base}/api/media/{quote(target, safe='/')}")
        assert status == 200, target
        assert body == wanted, target
    print(f"==> verified healthy API, {len(EXPECTED)} seeded Markdown notes, {len(MEDIA)} media files")


parser = argparse.ArgumentParser()
parser.add_argument("command", choices=("seed", "verify"))
parser.add_argument("--url", required=True)
args = parser.parse_args()
try:
    {"seed": seed, "verify": verify}[args.command](args.url.rstrip("/"))
except (AssertionError, HTTPError, OSError, ValueError) as error:
    print(f"tester-env {args.command} failed: {error}", file=sys.stderr)
    sys.exit(1)

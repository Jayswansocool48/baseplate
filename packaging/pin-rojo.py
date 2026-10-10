#!/usr/bin/env python3
"""Write packaging/rojo.json: the Flatpak module that bundles Rojo.

    python3 packaging/pin-rojo.py            # newest Rojo release
    python3 packaging/pin-rojo.py 7.7.0      # a specific version

Downloads the official Linux x86_64 build once to record its checksum.
"""
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/rojo-rbx/rojo/releases"
OUT = Path(__file__).resolve().parent / "rojo.json"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "roblox-vault-build"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else None
    release = json.loads(get(f"{API}/tags/v{version}" if version else f"{API}/latest"))
    asset = next((a for a in release["assets"]
                  if a["name"].endswith("linux-x86_64.zip")), None)
    if not asset:
        sys.exit(f"No linux-x86_64.zip in Rojo {release['tag_name']}")
    sha = hashlib.sha256(get(asset["browser_download_url"])).hexdigest()
    module = {
        "name": "rojo",
        "buildsystem": "simple",
        "build-commands": ["install -Dm755 rojo /app/bin/rojo"],
        "sources": [{
            "type": "archive",
            "url": asset["browser_download_url"],
            "sha256": sha,
            "strip-components": 0,
        }],
    }
    OUT.write_text(json.dumps(module, indent=2) + "\n")
    print(f"Pinned Rojo {release['tag_name']} ({sha[:12]}…) in {OUT.name}")


if __name__ == "__main__":
    main()

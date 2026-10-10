#!/usr/bin/env bash
# Release an update:   ./packaging/release.sh 1.1.0 "Faster preview; new sounds"
# Sets the version, adds release notes for the COSMIC Store, and pushes.
# GitHub then builds it and the COSMIC Store offers the update.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ID=io.github.jayswansocool48.RobloxVault
cd "$ROOT"

version="${1:-}"; notes="${2:-}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && -n "$notes" ]] || {
  echo "Usage: $0 1.1.0 \"What changed\""; exit 1; }
git diff --quiet && git diff --cached --quiet || {
  echo "Commit or stash your changes first."; exit 1; }

python3 -m unittest discover -t . -s tests

python3 - "$version" "$notes" "$ID" <<'PY'
import datetime, re, sys
from pathlib import Path
from xml.sax.saxutils import escape
version, notes, app_id = sys.argv[1:]
core = Path("roblox_vault/core.py")
core.write_text(re.sub(r'APP_VERSION = "[^"]*"', f'APP_VERSION = "{version}"', core.read_text()))
meta = Path(f"data/{app_id}.metainfo.xml")
text = meta.read_text()
if f'version="{version}"' in text:
    sys.exit(f"{version} is already released.")
today = datetime.date.today().isoformat()
entry = (f'    <release version="{version}" date="{today}">\n'
         f'      <description>\n        <p>{escape(notes)}</p>\n      </description>\n'
         f'    </release>\n')
meta.write_text(text.replace("  <releases>\n", "  <releases>\n" + entry, 1))
PY

git add roblox_vault/core.py "data/$ID.metainfo.xml"
git commit -q -m "Release $version"
git tag "v$version"
git push -q origin HEAD "v$version"
gh release create "v$version" --title "Roblox Vault $version" --notes "$notes" >/dev/null
echo "Released $version. GitHub is building it now; the COSMIC Store offers it in about 10 minutes."

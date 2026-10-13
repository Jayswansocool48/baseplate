#!/usr/bin/env bash
# Build Baseplate as a Flatpak on this computer and install it (for testing
# changes before you publish them).   ./packaging/build.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ID=io.github.jayswansocool48.Baseplate
cd "$ROOT"

flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
if ! command -v flatpak-builder >/dev/null; then
  flatpak install --user -y flathub org.flatpak.Builder
  BUILDER=(flatpak run org.flatpak.Builder)
else
  BUILDER=(flatpak-builder)
fi

python3 -m unittest discover -t . -s tests
[[ -f packaging/rojo.json ]] || python3 packaging/pin-rojo.py

"${BUILDER[@]}" --user --install --force-clean --install-deps-from=flathub \
  --default-branch=stable build "packaging/$ID.yml"
echo "Installed. Open Baseplate from your app launcher, or run: flatpak run $ID"

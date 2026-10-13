#!/usr/bin/env bash
# One command: put Baseplate on GitHub, publish it, and install it.
#
#   ./packaging/publish-setup.sh
#
# 1. Creates the GitHub repo with your github-kit (public, so the free GitHub
#    Pages can host the app) and lists it in your apps catalog.
# 2. Makes a signing key so your computer can trust the updates.
# 3. Turns on GitHub Pages and starts the first build.
# 4. Installs the app. Updates then show up in the COSMIC Store.
# 5. Removes the old zip version's launcher (your projects are kept and
#    copied into the new app on first start).
#
# Safe to run again: steps already done are skipped.
set -euo pipefail

NAME=baseplate
APP_ID=io.github.jayswansocool48.Baseplate
DESCRIPTION="Store, design, preview and sync Roblox systems with Studio, on Pop!_OS"
PROJECTS="${PROJECTS_DIR:-$HOME/Projects}"
KIT="$PROJECTS/apps/github-kit"
KEY_BACKUP="$HOME/.config/baseplate-publishing/signing-key.asc"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

step() { printf '\n== %s\n' "$1"; }

step "Checking GitHub sign-in"
if ! command -v gh >/dev/null || ! gh auth status >/dev/null 2>&1; then
  [[ -x "$KIT/setup.sh" ]] || gh repo clone Jayswansocool48/apps "$PROJECTS/apps"
  "$KIT/setup.sh"
fi
OWNER="$(gh api user --jq .login)"
REPO="$OWNER/$NAME"

step "Putting the app on GitHub"
if gh repo view "$REPO" >/dev/null 2>&1; then
  echo "github.com/$REPO already exists."
  ROOT="$HERE"
  git -C "$ROOT" rev-parse >/dev/null 2>&1 || ROOT="$PROJECTS/$NAME"
else
  [[ -x "$KIT/add-app.sh" ]] || gh repo clone "$OWNER/apps" "$PROJECTS/apps"
  COMMIT_MESSAGE="Add Baseplate" "$KIT/add-app.sh" "$NAME" "$HERE" --public \
    --description "$DESCRIPTION"
  ROOT="$PROJECTS/$NAME"
fi
cd "$ROOT"

step "Setting up the update signing key"
if gh secret list --repo "$REPO" | grep -q '^FLATPAK_GPG_KEY'; then
  echo "Already set."
else
  GNUPGHOME="$(mktemp -d)"; export GNUPGHOME
  trap 'rm -rf "$GNUPGHOME"' EXIT
  gpg --batch --pinentry-mode loopback --passphrase '' --quick-gen-key \
    "Baseplate updates <$OWNER@users.noreply.github.com>" rsa4096 sign never 2>/dev/null
  mkdir -p "$(dirname "$KEY_BACKUP")"
  (umask 077; gpg --batch --armor --export-secret-keys > "$KEY_BACKUP")
  gh secret set FLATPAK_GPG_KEY --repo "$REPO" < "$KEY_BACKUP"
  echo "Done. A private backup is in $KEY_BACKUP (never share or commit it)."
fi

step "Turning on GitHub Pages"
if gh api "repos/$REPO/pages" >/dev/null 2>&1; then
  gh api -X PUT "repos/$REPO/pages" -f build_type=workflow >/dev/null
else
  gh api -X POST "repos/$REPO/pages" -f build_type=workflow >/dev/null
fi
URL="https://$(echo "$OWNER" | tr '[:upper:]' '[:lower:]').github.io/$NAME"
echo "$URL"

step "Building and publishing (about 10 minutes the first time)"
for try in 1 2 3 4 5 6; do  # a brand-new repo needs a moment to list its workflows
  gh workflow run flatpak.yml --repo "$REPO" --ref main 2>/dev/null && break
  sleep 10
done
sleep 8
RUN="$(gh run list --repo "$REPO" --workflow flatpak.yml --event workflow_dispatch \
        --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "$RUN" --repo "$REPO" --exit-status

step "Installing Baseplate"
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
for try in 1 2 3 4 5; do
  if flatpak install --user -y --noninteractive "$URL/baseplate.flatpakref"; then
    break
  fi
  echo "GitHub Pages is still updating, trying again in 30 seconds…"; sleep 30
done
flatpak info --user "$APP_ID" >/dev/null

step "Removing the old zip version's launcher"
rm -rf "$HOME/.local/share/roblox-vault-app" "$HOME/.local/bin/roblox-vault" \
       "$HOME/.local/share/applications/io.github.robloxvault.RobloxVault.desktop"
echo "Done. Your old projects are copied into the new app when it first starts."

step "All set"
echo "Open Baseplate from your app launcher."
echo "To release an update later:  ./packaging/release.sh 1.1.0 \"What changed\""

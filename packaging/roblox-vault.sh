#!/bin/sh
# Starts Roblox Vault inside the Flatpak.
export PYTHONPATH="/app/share/roblox-vault${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m roblox_vault "$@"

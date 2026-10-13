#!/bin/sh
# Starts Baseplate inside the Flatpak.
export PYTHONPATH="/app/share/baseplate${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m baseplate "$@"

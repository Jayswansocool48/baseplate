"""Short sound effects. Off when the user (or the system) turns them off.

Sounds always go with a visible message, so nothing is said by sound alone.
"""
from __future__ import annotations

from pathlib import Path

SOUND_DIR = Path(__file__).parent / "sounds"
NAMES = ("success", "import", "error", "click", "sync_on", "sync_off", "delete")


class Sounds:
    def __init__(self, settings):
        self.settings = settings
        self._media = {}

    @property
    def enabled(self) -> bool:
        value = self.settings.get("sounds")
        if value is None:  # first run: follow the system's event-sounds setting
            try:
                from gi.repository import Gtk
                return bool(Gtk.Settings.get_default().get_property("gtk-enable-event-sounds"))
            except Exception:  # noqa: BLE001
                return True
        return bool(value)

    def set_enabled(self, on: bool):
        self.settings.set("sounds", bool(on))

    def play(self, name: str):
        if not self.enabled or name not in NAMES:
            return
        try:
            from gi.repository import Gtk
            media = self._media.get(name)
            if media is None:
                media = Gtk.MediaFile.new_for_filename(str(SOUND_DIR / f"{name}.wav"))
                self._media[name] = media
            media.set_volume(0.7)
            media.seek(0)
            media.play()
        except Exception:  # noqa: BLE001 - a missing audio backend must never break the app
            pass

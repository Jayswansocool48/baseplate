THIRD-PARTY SOFTWARE & LICENSES
Version 2026-10-12

Audit of everything the app uses. None of these collect or send data.

Bundled in the app:
- Rojo (rojo.space), official Linux build, for Studio sync and place files.
  Mozilla Public License 2.0. Source code: https://github.com/rojo-rbx/rojo
  It only runs when you press Sync or Build.

Provided by the GNOME Flatpak runtime (from Flathub, shared with other apps):
- Python 3 - PSF License
- GTK 4, libadwaita, GtkSourceView 5, PyGObject - LGPL 2.1 or later
- WebKitGTK 6 (Figma tab) - LGPL 2.1 / BSD
- GStreamer (plays the sound effects) - LGPL 2.1 or later

Online services, only if you open the Figma tab (optional):
- figma.com, shown in the Figma tab through WebKitGTK. Figma's website runs its
  own code and cookies there; see Figma's privacy and cookie policies.
- Figma REST API (api.figma.com) - read-only access to frames you import.
  No Figma SDK is bundled; the app uses Python's built-in urllib.

Updates: GitHub Pages hosts the app's update repository. No GitHub code runs
in the app.

Fonts, icon and sounds:
- Fonts: your system's fonts. The app ships none.
- App icon: original artwork made for Roblox Vault (MIT License).
- Sound effects: generated from scratch by tools/make_sounds.py, no samples
  (MIT License).
- Other icons come from your system icon theme.

What the app is allowed to do (Flatpak permissions), and why:
- Show windows (Wayland/X11), use the graphics card: to draw the app and the
  Figma tab.
- Network: for the Figma tab and Figma imports, and for Rojo to talk to
  Roblox Studio on this computer.
- Sound: for the sound effects (you can turn them off in the menu).
- Read ~/.local/share/roblox-vault: only to copy projects from the older zip
  version, once. Read-only.
- Talk to Flatpak: so "Uninstall Roblox Vault..." can remove the app itself and
  the older version's files. This is a powerful permission (it can run commands
  outside the sandbox); the app uses it only for uninstalling, after you
  confirm.

Roblox Vault itself: MIT License.

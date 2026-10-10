PRIVACY POLICY
Version 2026-10-11

Who we are
Roblox Vault is made by {owner_name}. Contact: {contact}

Short version
Roblox Vault collects nothing. Everything you make stays on your computer.
The only online part, the optional Figma tab, does nothing until you open it.

What is stored, and where
Everything lives in the app's own folder, ~/.var/app/io.github.jayswansocool48.RobloxVault :
- Your projects, scripts, GUIs and notes: data/roblox-vault/projects
- Your settings, sound on/off and the date you accepted these terms:
  config/roblox-vault/settings.json
- Your Figma token, only if you connect Figma: config/roblox-vault/figma-token
- Figma's own cookies for the Figma tab, only if you open it:
  data/roblox-vault/figma-web
- Which GUIs came from which Figma frame: figma-links.json inside each project
These files never leave your computer unless you copy them somewhere yourself.

Projects from the older zip version. On first start the app reads
~/.local/share/roblox-vault/projects (read-only) and copies any projects it
finds into its own folder. It never changes or uploads the originals.

What is NOT collected
No account, name, email, age, location, device ID, analytics, crash reports,
advertising IDs, or usage tracking. The app contains no third-party SDKs that
collect data (see "Third-Party Software & Licenses").

Network
By default the app does not connect to the internet.

Figma tab (optional). The Figma tab is a small web browser showing figma.com.
It loads nothing until you open it. While you use it, you are using Figma's
website directly: Figma receives what any browser sends it and stores its own
sign-in cookies (see above). That is covered by Figma's privacy policy, not
this one. Menu -> Figma -> Sign out deletes them.

Connecting Figma. To import designs, the app needs a Figma access token. When
you press Connect, the app watches your clipboard ONLY while the blue
"Connecting" bar is showing, ONLY looks for text starting with "figd_", and
ignores everything else. When it finds your token it stops watching, checks it
with Figma once, saves it (readable only by your user account) and wipes it
from the clipboard.

Importing. When you press Import or Update, the app sends the token and the
file/frame ID to api.figma.com and reads back that frame's layers. Nothing
about you or your projects is uploaded.

Sync. When you turn on Sync, Rojo listens only on "localhost", so only
programs on your own computer (Roblox Studio) can connect to it. What Roblox
Studio does with your game is covered by Roblox's own privacy policy.

Updates. The COSMIC Store (Flatpak) checks GitHub Pages for new versions of
the app, the same way it checks Flathub for your other apps. GitHub sees that
request; the app itself sends nothing.

Children
Because the app collects no personal information from anyone, it does not
collect personal information from children under 13 (or under the age set by
your country's law). The age question on first launch is only asked so that
younger users get a parent's OK; your answer is stored only on your computer.

Deleting your data
- Menu -> "Delete all my data..." removes every project, setting, the Figma
  token, the Figma tab's cookies and your consent record at once.
- Menu -> "Uninstall Roblox Vault..." does all of that, removes the app and its
  icon, and also removes files left by the older zip version.
- Uninstalling from the COSMIC Store, or with
  "flatpak uninstall --delete-data io.github.jayswansocool48.RobloxVault",
  removes the app folder listed above.

Changes
If this policy changes, the app shows it again and asks before you continue.

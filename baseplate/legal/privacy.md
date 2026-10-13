PRIVACY POLICY
Version 2026-10-13

Who we are
Baseplate is made by {owner_name}. Contact: {contact}

Short version
Baseplate collects nothing. Everything you make stays on your computer. It
only goes online when you use the Figma tab, or the assistant with Claude or
ChatGPT. With Ollama, the assistant runs entirely on your computer.

What is stored, and where
Everything lives in the app's own folder, ~/.var/app/io.github.jayswansocool48.Baseplate :
- Your projects, scripts, GUIs and notes: data/baseplate/projects
- Your settings (assistant choice, sound on/off, which cloud assistants you
  agreed to use) and the date you accepted these terms:
  config/baseplate/settings.json
- Your Claude or ChatGPT API keys, only if you add them:
  config/baseplate/ai-keys.json (readable only by your user account)
- Your Figma token, only if you connect Figma: config/baseplate/figma-token
- Figma's own cookies for the Figma tab, only if you open it:
  data/baseplate/figma-web
- Which GUIs came from which Figma frame: figma-links.json inside each project
Assistant chats are kept only while the app is open and are not saved.
None of these files leave your computer unless you copy them yourself.

Projects from Roblox Vault. Baseplate used to be called Roblox Vault. On first
start it reads the old projects folders (read-only) and copies your projects
in. It can then remove the old app if you agree. It never uploads them.

What is NOT collected
No account, name, email, age, location, device ID, analytics, crash reports,
advertising IDs, or usage tracking. The app contains no third-party SDKs that
collect data (see "Third-Party Software & Licenses").

AI assistant
You choose which assistant to use in Assistant settings:
- Ollama: runs on your computer. Nothing is sent anywhere.
- Claude (Anthropic) or ChatGPT (OpenAI): when you send a message, the app
  sends it, the earlier messages of that chat, and only what you ticked under
  "Share" (the open file, and/or the project's file names and notes.md) to
  Anthropic or OpenAI, using your own API key. Nothing else from your projects
  is uploaded. The first time you use each one, the app tells you this and asks
  before sending. What Anthropic or OpenAI do with it is covered by their own
  privacy policies and API terms.

Figma tab (optional). The Figma tab is a small web browser showing figma.com.
It loads nothing until you open it. While you use it, you are using Figma's
website directly: Figma receives what any browser sends it and stores its own
sign-in cookies (see above). That is covered by Figma's privacy policy, not
this one. Menu -> Figma -> Sign out deletes them.

Connecting Figma. When you press Connect, the app watches your clipboard ONLY
while the "Connecting" bar is showing, ONLY looks for text starting with
"figd_", and ignores everything else. When it finds your token it stops
watching, saves it and wipes it from the clipboard. Nothing is sent to Figma
until you import. If Figma rejects the token, the app deletes it.

Importing. When you press Import or Update, the app sends the token and the
file/frame ID to api.figma.com and reads back that frame's layers.

Sync. When you turn on Sync, Rojo listens only on "localhost", so only
programs on your own computer (Roblox Studio) can connect to it.

Updates. The COSMIC Store checks GitHub Pages for new versions of the app.
GitHub sees that request; the app itself sends nothing.

Children
The app collects no personal information from anyone, including children
under 13. The age question on first launch makes sure younger users have a
parent's OK. Claude and ChatGPT have their own age rules (see the Terms); a
younger user should use Ollama or ask a parent.

Deleting your data
- Menu -> "Delete all my data..." removes every project, setting, API key, the
  Figma token, the Figma tab's cookies and your consent record.
- Menu -> "Uninstall Baseplate..." does all of that, removes the app and its
  icon, and also removes Roblox Vault and the older zip version's files.
- Uninstalling from the COSMIC Store, or with
  "flatpak uninstall --delete-data io.github.jayswansocool48.Baseplate",
  removes the app folder listed above.
- Messages already sent to Anthropic or OpenAI are handled under their
  policies; contact them to delete those.

Changes
If this policy changes, the app shows it again and asks before you continue.

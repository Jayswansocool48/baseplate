"""Roblox Vault core: storage, projects, scripts, GUIs and Rojo sync.

No GTK imports here, so this module can be tested headless.
Everything is stored locally. Nothing is ever sent over the network.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

APP_ID = "io.github.jayswansocool48.RobloxVault"
APP_NAME = "Roblox Vault"
APP_VERSION = "1.0.0"
LEGAL_VERSION = "2026-10-11"  # bump when legal docs change -> asks for consent again
DEFAULT_PORT = 34872  # Rojo's default port

SCRIPT_KINDS = {
    "Script": ".server.luau",
    "LocalScript": ".client.luau",
    "ModuleScript": ".luau",
}

# folder in src/  ->  where it lands in Roblox
FOLDERS = {
    "server": "ServerScriptService",
    "client": "StarterPlayerScripts",
    "shared": "ReplicatedStorage",
    "gui": "StarterGui",
}

NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_ \-]{0,63}$")
# Version / status suffixes are refused so every name stays the single source
# of truth: "InventoryV2", "Weapon_Final", "PlayerMovement New", "Health-old"...
_STATUS = r"(?:new|final|updated|update|old|copy|backup|temp|fixed|revised|latest)"
VERSION_SUFFIX_RE = re.compile(
    r"(?:(?:[ _\-][vV]|(?<=[a-z0-9])V)\d+(?:[._]\d+)*"  # InventoryV2, _v3, -v1.2
    rf"|[ _\-](?i:{_STATUS})"                    # _New, -final, " Old"
    r"|(?<=[a-z0-9])(?:New|Final|Updated|Update|Old|Copy|Backup|Temp|Fixed|Revised|Latest)"
    r")$")

IN_FLATPAK = Path("/.flatpak-info").exists()
EDITABLE_SUFFIXES = (".luau", ".lua", ".json", ".txt", ".toml", ".md")


class VaultError(Exception):
    """A problem worth showing to the user as-is."""


# ---------------------------------------------------------------- paths

def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "roblox-vault"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "roblox-vault"


def projects_dir() -> Path:
    p = data_dir() / "projects"
    p.mkdir(parents=True, exist_ok=True)
    return p


def validate_name(name: str) -> str:
    name = (name or "").strip()
    if not NAME_RE.match(name):
        raise VaultError(
            "Names can use letters, numbers, spaces, - and _ (max 64 characters)."
        )
    if VERSION_SUFFIX_RE.search(name):
        raise VaultError(
            f'"{name}" ends in a version or status tag. Use one clean name, like '
            f'"{strip_version_suffix(name) or "Inventory"}", and change the existing one instead.'
        )
    return name


def strip_version_suffix(name: str) -> str:
    """'Inventory V2' -> 'Inventory', 'Weapon_Final_old' -> 'Weapon'."""
    prev = None
    while prev != name:
        prev, name = name, VERSION_SUFFIX_RE.sub("", name).rstrip(" _-")
    return name


def _inside(root: Path, target: Path) -> Path:
    """Refuse any path that escapes root (e.g. '../../.bashrc')."""
    root = root.resolve()
    target = target.resolve()
    if target != root and root not in target.parents:
        raise VaultError("That path is outside the project.")
    return target


# ---------------------------------------------------------------- settings

class Settings:
    """Small JSON settings file. Holds only consent and UI choices."""

    def __init__(self):
        self.path = config_dir() / "settings.json"
        self.data = {"consent": None, "port": DEFAULT_PORT}
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text()))
            except (OSError, json.JSONDecodeError):
                pass  # corrupt file -> fall back to defaults

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2))
        tmp.replace(self.path)

    @property
    def has_consent(self) -> bool:
        c = self.data.get("consent") or {}
        return bool(c.get("terms") and c.get("privacy") and c.get("age")
                    and c.get("version") == LEGAL_VERSION)

    def record_consent(self, terms: bool, privacy: bool, age: bool):
        self.data["consent"] = {
            "terms": terms, "privacy": privacy, "age": age,
            "version": LEGAL_VERSION,
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.save()

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    @property
    def port(self) -> int:
        try:
            return int(self.data.get("port", DEFAULT_PORT))
        except (TypeError, ValueError):
            return DEFAULT_PORT


# ---------------------------------------------------------------- projects

def project_path(name: str) -> Path:
    return _inside(projects_dir(), projects_dir() / validate_name(name))


def list_projects() -> list[str]:
    return sorted(p.name for p in projects_dir().iterdir()
                  if p.is_dir() and (p / "default.project.json").exists())


def create_project(name: str) -> Path:
    path = project_path(name)
    if path.exists():
        raise VaultError(f'A project called "{name}" already exists.')
    for folder in FOLDERS:
        (path / "src" / folder).mkdir(parents=True)
    (path / "notes.md").write_text(f"# {name}\n\nWhat this system does:\n")
    write_project_file(name)
    return path


def delete_project(name: str):
    shutil.rmtree(project_path(name))


def write_project_file(name: str):
    """(Re)generate default.project.json. Each GUI in src/gui becomes a
    direct child of StarterGui so Roblox copies it into PlayerGui."""
    path = project_path(name)
    starter_gui: dict = {"$className": "StarterGui"}
    for f in sorted((path / "src" / "gui").glob("*.model.json")):
        starter_gui[f.name[: -len(".model.json")]] = {"$path": f"src/gui/{f.name}"}
    tree = {
        "name": name,
        "tree": {
            "$className": "DataModel",
            "ServerScriptService": {
                "$className": "ServerScriptService",
                "Server": {"$path": "src/server"},
            },
            "ReplicatedStorage": {
                "$className": "ReplicatedStorage",
                "Shared": {"$path": "src/shared"},
            },
            "StarterPlayer": {
                "$className": "StarterPlayer",
                "StarterPlayerScripts": {
                    "$className": "StarterPlayerScripts",
                    "Client": {"$path": "src/client"},
                },
            },
            "StarterGui": starter_gui,
        },
    }
    (path / "default.project.json").write_text(json.dumps(tree, indent=2) + "\n")


def list_files(name: str) -> list[str]:
    """Relative paths of editable files, notes first."""
    path = project_path(name)
    out = ["notes.md"] if (path / "notes.md").exists() else []
    src = path / "src"
    for f in sorted(src.rglob("*")):
        if f.is_file() and f.name.endswith(EDITABLE_SUFFIXES):
            out.append(str(f.relative_to(path)))
    return out


def read_file(name: str, rel: str) -> str:
    return _inside(project_path(name), project_path(name) / rel).read_text()


def write_file(name: str, rel: str, text: str):
    target = _inside(project_path(name), project_path(name) / rel)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(target)


def delete_file(name: str, rel: str):
    if rel == "notes.md":
        raise VaultError("Notes can't be deleted, but you can clear them.")
    _inside(project_path(name), project_path(name) / rel).unlink()
    if rel.startswith("src/gui/"):
        write_project_file(name)


SCRIPT_TEMPLATES = {
    "Script": '-- {name} (server)\n\nlocal Players = game:GetService("Players")\n\n'
              'Players.PlayerAdded:Connect(function(player)\n'
              '\tprint("[{name}] joined:", player.Name)\nend)\n',
    "LocalScript": '-- {name} (client)\n\nlocal player = game:GetService("Players").LocalPlayer\n\n'
                   'print("[{name}] running for", player.Name)\n',
    "ModuleScript": "-- {name} (module)\n\nlocal {ident} = {{}}\n\n"
                    "function {ident}.hello()\n\treturn \"hello from {name}\"\nend\n\n"
                    "return {ident}\n",
}


def create_script(project: str, folder: str, name: str, kind: str) -> str:
    if folder not in ("server", "client", "shared"):
        raise VaultError("Pick server, client or shared.")
    if kind not in SCRIPT_KINDS:
        raise VaultError("Unknown script type.")
    name = validate_name(name)
    rel = f"src/{folder}/{name}{SCRIPT_KINDS[kind]}"
    target = project_path(project) / rel
    if target.exists():
        raise VaultError(f'"{name}" already exists there.')
    ident = re.sub(r"\W", "_", name) or "Module"
    target.write_text(SCRIPT_TEMPLATES[kind].format(name=name, ident=ident))
    return rel


def gui_template(name: str) -> dict:
    """A simple, readable starter ScreenGui in Rojo's JSON model format."""
    return {
        "ClassName": "ScreenGui",
        "Properties": {"ResetOnSpawn": {"Bool": False}},
        "Children": [{
            "Name": "Main",
            "ClassName": "Frame",
            "Properties": {
                "AnchorPoint": {"Vector2": [0.5, 0.5]},
                "Position": {"UDim2": [[0.5, 0], [0.5, 0]]},
                "Size": {"UDim2": [[0, 320], [0, 180]]},
                "BackgroundColor3": {"Color3": [0.11, 0.11, 0.13]},
            },
            "Children": [
                {"Name": "Corner", "ClassName": "UICorner"},
                {
                    "Name": "Title",
                    "ClassName": "TextLabel",
                    "Properties": {
                        "Size": {"UDim2": [[1, 0], [0, 48]]},
                        "BackgroundTransparency": {"Float32": 1},
                        "Text": {"String": name},
                        "TextColor3": {"Color3": [1, 1, 1]},
                        "TextSize": {"Float32": 24},
                    },
                },
            ],
        }],
    }


def create_gui(project: str, name: str) -> str:
    name = validate_name(name)
    rel = f"src/gui/{name}.model.json"
    target = project_path(project) / rel
    if target.exists():
        raise VaultError(f'A GUI called "{name}" already exists.')
    target.write_text(json.dumps(gui_template(name), indent=2) + "\n")
    write_project_file(project)
    return rel


# ---------------------------------------------------------------- rojo

def find_rojo() -> str | None:
    found = shutil.which("rojo")
    if found:
        return found
    home = Path.home()
    for c in (".rokit/bin/rojo", ".aftman/bin/rojo", ".cargo/bin/rojo"):
        if (home / c).is_file():
            return str(home / c)
    return None


def rojo_build(project: str, out_file: str) -> str:
    rojo = find_rojo()
    if not rojo:
        raise VaultError("Rojo isn't installed. See Help → Setting up sync.")
    write_project_file(project)
    if not out_file.endswith((".rbxm", ".rbxmx", ".rbxl", ".rbxlx")):
        out_file += ".rbxl"
    r = subprocess.run([rojo, "build", "--output", out_file],
                       cwd=project_path(project), capture_output=True, text=True)
    if r.returncode != 0:
        raise VaultError(r.stderr.strip() or "Rojo build failed.")
    return out_file


class RojoServer:
    """Runs `rojo serve` for one project; streams output to a callback."""

    def __init__(self, on_output, on_exit):
        self.proc: subprocess.Popen | None = None
        self.project: str | None = None
        self._on_output, self._on_exit = on_output, on_exit

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, project: str, port: int):
        if self.running:
            raise VaultError(f'Already syncing "{self.project}". Stop it first.')
        rojo = find_rojo()
        if not rojo:
            raise VaultError("Rojo isn't installed. See Help → Setting up sync.")
        write_project_file(project)
        # --address localhost: only this computer can connect.
        self.proc = subprocess.Popen(
            [rojo, "serve", "--address", "localhost", "--port", str(port)],
            cwd=project_path(project), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.project = project
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        proc = self.proc
        for line in proc.stdout:
            self._on_output(line)
        proc.wait()
        self._on_exit(proc.returncode)

    def stop(self):
        if self.running:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.project = None


# ---------------------------------------------------------------- deletion

def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "roblox-vault"


def delete_all_data():
    """Data deletion request: removes every project, setting, token and cookie."""
    for d in (data_dir(), config_dir(), cache_dir()):
        if d.exists():
            shutil.rmtree(d)


# ---------------------------------------------------------------- legacy install

# Where the earlier zip version (install.sh) put things, relative to $HOME.
LEGACY_FILES = [
    ".local/share/roblox-vault-app",
    ".local/bin/roblox-vault",
    ".local/share/applications/io.github.robloxvault.RobloxVault.desktop",
]
LEGACY_DATA = [".local/share/roblox-vault", ".config/roblox-vault"]


def host_home() -> Path:
    """The real home folder, also inside the Flatpak sandbox."""
    return Path(os.environ.get("HOME") or os.path.expanduser("~"))


def migrate_legacy_projects() -> int:
    """Copy projects from the zip version into this install, once.
    Returns how many projects were copied. Never deletes the originals."""
    if not IN_FLATPAK:
        return 0  # same folder; nothing to move
    old = host_home() / ".local/share/roblox-vault/projects"
    marker = config_dir() / "migrated"
    if marker.exists() or not old.is_dir():
        return 0
    copied = 0
    for p in sorted(old.iterdir()):
        target = projects_dir() / p.name
        if p.is_dir() and (p / "default.project.json").exists() and not target.exists():
            shutil.copytree(p, target)
            copied += 1
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("done\n")
    return copied


# ---------------------------------------------------------------- uninstall

def uninstall_commands(home: Path | None = None) -> list[list[str]]:
    """Host commands that remove the app itself and everything the zip
    version left behind. Run after delete_all_data()."""
    home = home or host_home()
    legacy = [str(home / p) for p in LEGACY_FILES + LEGACY_DATA]
    cmds = [["rm", "-rf", "--", *legacy]]
    if IN_FLATPAK:
        # Remove from whichever installation has it (user first, then system).
        cmds.append(["sh", "-c",
                     f"sleep 2; flatpak uninstall --user -y --delete-data {APP_ID} "
                     f"|| flatpak uninstall --system -y --delete-data {APP_ID}"])
    return cmds


def can_reach_host() -> bool:
    """True when the Flatpak lets us run commands on the host (needed to
    remove the app itself)."""
    if not IN_FLATPAK:
        return True
    try:
        info = Path("/.flatpak-info").read_text()
    except OSError:
        return False
    return "org.freedesktop.Flatpak=talk" in info


def uninstall_app():
    """Uninstall button: delete all data, then remove the app.
    Returns True if the app itself is being removed, False if only the data
    could be deleted (the caller then points the user to the COSMIC Store)."""
    delete_all_data()
    if not can_reach_host():
        return False
    for cmd in uninstall_commands():
        if IN_FLATPAK:
            # detached on the host so it finishes after this app quits
            subprocess.Popen(["flatpak-spawn", "--host", "setsid", *cmd],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        else:
            subprocess.run(cmd, check=False)
    return True

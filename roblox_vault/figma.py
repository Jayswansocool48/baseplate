"""Figma -> Roblox GUI import.

The app shows figma.com in its own Figma tab. The user picks a frame there and
presses Import; the frame is read through Figma's REST API and converted to a
Rojo .model.json ScreenGui.

Network use is opt-in: nothing here runs until the user connects Figma.
The access token is stored locally (owner-only permissions) and sent only to
api.figma.com.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from . import core

API = "https://api.figma.com/v1"
HOME_URL = "https://www.figma.com/files"
LINKS_FILE = "figma-links.json"  # project root, outside src/, so Rojo ignores it
TOKEN_RE = re.compile(r"figd_[A-Za-z0-9_\-]{20,}")

TEXT_X = {"LEFT": 0, "RIGHT": 1, "CENTER": 2, "JUSTIFIED": 0}
TEXT_Y = {"TOP": 0, "CENTER": 1, "BOTTOM": 2}
CONTAINER_TYPES = {"FRAME", "GROUP", "COMPONENT", "COMPONENT_SET", "INSTANCE", "SECTION"}
SHAPE_TYPES = {"RECTANGLE", "ELLIPSE", "VECTOR", "LINE", "STAR",
               "REGULAR_POLYGON", "BOOLEAN_OPERATION"}


class NameTaken(core.VaultError):
    """A different GUI already uses this frame's name. Carries the fetched
    frame so the import can finish under a new name without another request."""

    def __init__(self, name, frame, key, node_id):
        super().__init__(f'A GUI called "{name}" already exists.')
        self.name, self.frame, self.key, self.node_id = name, frame, key, node_id


class NeedsFrameChoice(core.VaultError):
    """The Figma tab has a file open but no frame selected."""

    def __init__(self, file_key: str, frames: list):
        super().__init__("Pick a frame.")
        self.file_key, self.frames = file_key, frames


# ---------------------------------------------------------------- storage

def web_data_dir():
    """Figma's own cookies/site data for the Figma tab (website data, not ours)."""
    return core.data_dir() / "figma-web"


def token_path():
    return core.config_dir() / "figma-token"


def get_token() -> str | None:
    try:
        return token_path().read_text().strip() or None
    except OSError:
        return None


def find_token(text: str | None) -> str | None:
    """Pull a Figma personal access token out of copied text, if there is one."""
    m = TOKEN_RE.search(text or "")
    return m.group(0) if m else None


def set_token(token: str):
    token = (token or "").strip()
    if not TOKEN_RE.fullmatch(token):
        raise core.VaultError("That doesn't look like a Figma token.")
    p = token_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token)


def disconnect(remove_web: bool = True):
    """Forget the token and (unless WebKit already cleared it) the Figma tab's
    sign-in and cookies."""
    try:
        token_path().unlink()
    except FileNotFoundError:
        pass
    if remove_web:
        import shutil
        shutil.rmtree(web_data_dir(), ignore_errors=True)


# ---------------------------------------------------------------- figma.com urls

def parse_url(url: str) -> tuple[str | None, str | None]:
    """Figma tab URL -> (file_key, node_id). Either can be None."""
    u = urllib.parse.urlparse(url or "")
    if not u.netloc.endswith("figma.com"):
        return None, None
    parts = [p for p in u.path.split("/") if p]
    if len(parts) < 2 or parts[0] not in ("design", "file", "proto"):
        return None, None
    key = parts[3] if len(parts) >= 4 and parts[2] == "branch" else parts[1]
    node = urllib.parse.parse_qs(u.query).get("node-id", [None])[0]
    return key, node.replace("-", ":") if node else None


# ---------------------------------------------------------------- api

def _get(path: str, params: dict | None = None, token: str | None = None) -> dict:
    token = token or get_token()
    if not token:
        raise core.VaultError("Connect Figma first.")
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"X-Figma-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise core.VaultError(_explain(e.code, _figma_reason(e)))
    except (urllib.error.URLError, TimeoutError):
        raise core.VaultError("Couldn't reach Figma. Check your internet connection.")


def _figma_reason(e) -> str:
    """Figma's own short error text ('Invalid token', ...), if it sent one."""
    try:
        body = json.loads(e.read() or b"{}")
    except (ValueError, OSError):
        return ""
    return str(body.get("err") or body.get("message") or "")[:200]


def _explain(code: int, reason: str) -> str:
    low = reason.lower()
    if code in (401, 403) and ("token" in low or "expired" in low or code == 401):
        disconnect(remove_web=False)  # next Import walks you through Connect again
        return ("Your Figma token was refused (" + (reason or "invalid") + "). "
                "Press Import again to connect a new one.")
    if code == 403:
        return ("Figma refused access" + (f" ({reason})" if reason else "") + ". "
                "Make sure the token has File content: read-only access and "
                "that you can open this file in the Figma tab.")
    if code == 404:
        return "Figma couldn't find that file. Do you have access to it?"
    if code == 429:
        return ("You've hit Figma's import limit for now. Free and View seats only "
                "get a few imports a month; it resets later.")
    return f"Figma error {code}" + (f": {reason}" if reason else ".")


def fetch_nodes(file_key: str, node_ids: list[str]) -> dict:
    """One request for many frames: {node_id: document or None}."""
    data = _get(f"/files/{urllib.parse.quote(file_key)}/nodes",
                {"ids": ",".join(node_ids)})
    return {nid: (n or {}).get("document") for nid, n in (data.get("nodes") or {}).items()}


def list_frames(file_key: str) -> list[dict]:
    """Top-level frames on every page: [{id, name, page}]."""
    data = _get(f"/files/{urllib.parse.quote(file_key)}", {"depth": 2})
    out = []
    for page in data.get("document", {}).get("children", []):
        for n in page.get("children", []):
            if n.get("type") in CONTAINER_TYPES:
                out.append({"id": n["id"], "name": n.get("name", "Frame"),
                            "page": page.get("name", "Page")})
    return out


# ---------------------------------------------------------------- conversion

def _color(c):
    return [round(c.get("r", 0), 4), round(c.get("g", 0), 4), round(c.get("b", 0), 4)]


def _solid(paints):
    for p in paints or []:
        if p.get("visible", True) and p.get("type") == "SOLID":
            alpha = p.get("color", {}).get("a", 1) * p.get("opacity", 1)
            return _color(p["color"]), round(1 - alpha, 4)
    return None


def _has_image(paints):
    return any(p.get("visible", True) and p.get("type") == "IMAGE" for p in paints or [])


def clean_name(name: str) -> str:
    """Figma layer name -> a valid Roblox name, minus version tags like 'V2'."""
    name = re.sub(r"[^A-Za-z0-9_ \-]", "", name or "").strip()[:64]
    name = core.strip_version_suffix(name)
    return name if core.NAME_RE.match(name or "") else "Element"


def _udim2(x, y, w, h, pw, ph, scale):
    if scale and pw and ph:
        return ({"UDim2": [[round(x / pw, 4), 0], [round(y / ph, 4), 0]]},
                {"UDim2": [[round(w / pw, 4), 0], [round(h / ph, 4), 0]]})
    return ({"UDim2": [[0, round(x)], [0, round(y)]]},
            {"UDim2": [[0, round(w)], [0, round(h)]]})


def _class_for(node):
    t, name = node.get("type"), node.get("name", "").lower()
    is_button = name.startswith(("button", "btn")) or name.endswith(("button", "btn"))
    if t == "TEXT":
        return "TextButton" if is_button else "TextLabel"
    if _has_image(node.get("fills")):
        return "ImageButton" if is_button else "ImageLabel"
    return "TextButton" if is_button else "Frame"


def convert_node(node, parent_box, scale, z, warnings):
    t = node.get("type")
    if t not in CONTAINER_TYPES | SHAPE_TYPES | {"TEXT"}:
        return None
    box = node.get("absoluteBoundingBox") or {}
    if not box:
        return None
    cls = _class_for(node)
    pos, size = _udim2(box["x"] - parent_box["x"], box["y"] - parent_box["y"],
                       box["width"], box["height"],
                       parent_box["width"], parent_box["height"], scale)
    props = {"Position": pos, "Size": size, "ZIndex": {"Int32": z},
             "BorderSizePixel": {"Int32": 0}}
    if not node.get("visible", True):
        props["Visible"] = {"Bool": False}

    children = []
    if t == "TEXT":
        style = node.get("style", {})
        fill = _solid(node.get("fills"))
        props.update({
            "BackgroundTransparency": {"Float32": 1},
            "Text": {"String": node.get("characters", "")},
            "TextSize": {"Float32": float(style.get("fontSize", 14))},
            "TextWrapped": {"Bool": True},
            "TextXAlignment": {"Enum": TEXT_X.get(style.get("textAlignHorizontal"), 0)},
            "TextYAlignment": {"Enum": TEXT_Y.get(style.get("textAlignVertical"), 0)},
        })
        if fill:
            props["TextColor3"] = {"Color3": fill[0]}
            props["TextTransparency"] = {"Float32": fill[1]}
    else:
        fill = _solid(node.get("fills"))
        if fill:
            props["BackgroundColor3"] = {"Color3": fill[0]}
            props["BackgroundTransparency"] = {"Float32": fill[1]}
        else:
            props["BackgroundTransparency"] = {"Float32": 1}
        if cls == "TextButton":
            props["Text"] = {"String": ""}
            props["AutoButtonColor"] = {"Bool": True}
        if cls in ("ImageLabel", "ImageButton"):
            warnings.append(f'"{node.get("name")}" uses an image: upload it to '
                            "Roblox and paste the rbxassetid into Image.")
        if node.get("clipsContent"):
            props["ClipsDescendants"] = {"Bool": True}
        if t == "ELLIPSE":
            children.append({"Name": "Corner", "ClassName": "UICorner",
                             "Properties": {"CornerRadius": {"UDim": [0.5, 0]}}})
        elif node.get("cornerRadius"):
            children.append({"Name": "Corner", "ClassName": "UICorner", "Properties": {
                "CornerRadius": {"UDim": [0, round(node["cornerRadius"])]}}})
        if t in SHAPE_TYPES - {"RECTANGLE", "ELLIPSE"}:
            warnings.append(f'"{node.get("name")}" is a {t.lower()}; Roblox only '
                            "gets its box. Export it as an image for the real shape.")

    stroke = _solid(node.get("strokes"))
    if stroke and node.get("strokeWeight"):
        children.append({"Name": "Stroke", "ClassName": "UIStroke", "Properties": {
            "Color": {"Color3": stroke[0]}, "Transparency": {"Float32": stroke[1]},
            "Thickness": {"Float32": float(node["strokeWeight"])},
            "ApplyStrokeMode": {"Enum": 1}}})  # Border

    if t in CONTAINER_TYPES:
        for i, child in enumerate(node.get("children", []), start=1):
            c = convert_node(child, box, scale, i, warnings)
            if c:
                children.append(c)

    out = {"Name": clean_name(node.get("name")), "ClassName": cls, "Properties": props}
    if children:
        out["Children"] = children
    return out


def to_screengui(frame, scale):
    if not frame or frame.get("type") not in CONTAINER_TYPES:
        raise core.VaultError("Select a frame in Figma, not a single layer.")
    warnings = []
    root = convert_node(frame, frame["absoluteBoundingBox"], scale, 1, warnings)
    rp = root["Properties"]
    if scale:
        rp["Position"] = {"UDim2": [[0, 0], [0, 0]]}
        rp["Size"] = {"UDim2": [[1, 0], [1, 0]]}
    else:
        rp["AnchorPoint"] = {"Vector2": [0.5, 0.5]}
        rp["Position"] = {"UDim2": [[0.5, 0], [0.5, 0]]}
    model = {"ClassName": "ScreenGui",
             "Properties": {"ResetOnSpawn": {"Bool": False},
                            "ZIndexBehavior": {"Enum": 1},
                            "IgnoreGuiInset": {"Bool": scale}},
             "Children": [root]}
    return model, warnings


# ---------------------------------------------------------------- project glue

def linked_guis(project):
    try:
        return json.loads((core.project_path(project) / LINKS_FILE).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_links(project, links):
    (core.project_path(project) / LINKS_FILE).write_text(json.dumps(links, indent=2) + "\n")


def _name_in_use(project, name):
    gui_dir = core.project_path(project) / "src" / "gui"
    return (gui_dir / f"{name}.model.json").exists() or name in linked_guis(project)


def _gui_name_for(project, frame, key, node_id):
    """Re-importing the same frame updates its GUI. A new frame is named after
    the Figma frame; if that name is taken, NameTaken asks the user for one
    (never 'Inventory2' style copies)."""
    for name, link in linked_guis(project).items():
        if link.get("key") == key and link.get("node") == node_id:
            return name
    name = clean_name(frame.get("name"))
    if name == "Element":
        name = "FigmaGui"
    if _name_in_use(project, name):
        raise NameTaken(name, frame, key, node_id)
    return name


def import_frame_as(project, name, frame, key, node_id, scale):
    """Finish an import under a name the user chose (after NameTaken)."""
    name = core.validate_name(name)
    if _name_in_use(project, name):
        raise NameTaken(name, frame, key, node_id)
    rel, warnings = _write_gui(project, name, frame, key, node_id, scale)
    return name, rel, warnings


def _write_gui(project, name, frame, key, node_id, scale):
    model, warnings = to_screengui(frame, scale)
    rel = f"src/gui/{name}.model.json"
    core.write_file(project, rel, json.dumps(model, indent=2) + "\n")
    links = linked_guis(project)
    links[name] = {"key": key, "node": node_id, "scale": scale,
                   "synced": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    _save_links(project, links)
    core.write_project_file(project)
    return rel, warnings


def import_from_tab(project, tab_url, scale, node_id=None, _fetch=fetch_nodes,
                    _frames=list_frames):
    """Import what's selected in the Figma tab. Raises NeedsFrameChoice when
    no frame is selected, carrying the file's frames for a picker."""
    key, url_node = parse_url(tab_url)
    if not key:
        raise core.VaultError("Open a design file in the Figma tab first.")
    node_id = node_id or url_node
    frame = _fetch(key, [node_id]).get(node_id) if node_id else None
    if not frame or frame.get("type") not in CONTAINER_TYPES:
        raise NeedsFrameChoice(key, _frames(key))
    name = _gui_name_for(project, frame, key, node_id)
    rel, warnings = _write_gui(project, name, frame, key, node_id, scale)
    return name, rel, warnings


def refresh_all(project, _fetch=fetch_nodes):
    """Re-pull linked GUIs, one Figma request per file. -> (names, problems)."""
    by_file: dict[str, list] = {}
    for name, link in linked_guis(project).items():
        if link.get("key") and link.get("node"):
            by_file.setdefault(link["key"], []).append((name, link))
    done, problems = [], []
    for key, items in by_file.items():
        try:
            nodes = _fetch(key, sorted({link["node"] for _n, link in items}))
        except core.VaultError as e:
            problems.append(str(e))
            continue
        for name, link in items:
            frame = nodes.get(link["node"])
            if not frame:
                problems.append(f"{name}: the frame was deleted in Figma.")
                continue
            try:
                _rel, warns = _write_gui(project, name, frame, key, link["node"],
                                         link.get("scale", False))
                done.append(name)
                problems += warns
            except core.VaultError as e:
                problems.append(f"{name}: {e}")
    return done, problems


def unlink(project, gui_name):
    links = linked_guis(project)
    if links.pop(gui_name, None) is not None:
        _save_links(project, links)

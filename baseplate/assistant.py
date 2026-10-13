"""AI assistant: Claude (Anthropic), ChatGPT (OpenAI) or Ollama (local, free).

No GTK here, so it can be tested headless. Network calls only happen when the
user sends a message or refreshes the model list. Cloud providers only get
what the user sends plus the context they chose to share; Ollama never leaves
this computer.
"""
from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass

from . import core


@dataclass(frozen=True)
class Provider:
    key: str
    name: str
    short: str
    cloud: bool
    default_model: str
    key_url: str = ""
    key_hint: str = ""
    company: str = ""


PROVIDERS = {
    "claude": Provider(
        "claude", "Claude (Anthropic)", "Claude", True, "claude-sonnet-5-5",
        "https://console.anthropic.com/settings/keys", "sk-ant-…", "Anthropic"),
    "openai": Provider(
        "openai", "ChatGPT (OpenAI)", "ChatGPT", True, "gpt-6.1-sol",
        "https://platform.openai.com/api-keys", "sk-…", "OpenAI"),
    "ollama": Provider(
        "ollama", "Ollama (free, runs on this computer)", "Ollama", False, ""),
}
DEFAULT_OLLAMA_URL = "http://localhost:11434"
ANTHROPIC_VERSION = "2023-06-01"
MAX_CONTEXT_CHARS = 24_000
TIMEOUT = 120


class AssistantError(core.BaseplateError):
    pass


# ---------------------------------------------------------------- keys

def _keys_path():
    return core.config_dir() / "ai-keys.json"


def get_key(provider: str) -> str | None:
    try:
        return json.loads(_keys_path().read_text()).get(provider) or None
    except (OSError, ValueError):
        return None


def set_key(provider: str, key: str | None):
    """Save (or with None, forget) an API key. Readable only by this user."""
    try:
        keys = json.loads(_keys_path().read_text())
    except (OSError, ValueError):
        keys = {}
    key = (key or "").strip()
    if key:
        if len(key) < 20 or any(c.isspace() for c in key):
            raise AssistantError("That doesn't look like an API key.")
        keys[provider] = key
    else:
        keys.pop(provider, None)
    p = _keys_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(keys, f)


# ---------------------------------------------------------------- prompt

SYSTEM_PROMPT = """You are the coding assistant inside Baseplate, a desktop app for building \
Roblox systems (inventory, shops, quests, GUIs) as Rojo projects that sync into Roblox Studio.

Write Luau for Roblox. Prefer modern APIs (task.wait, task.spawn, \
Instance:GetAttribute, RemoteEvents with server-side validation). Never trust the client.

Project layout: src/server = Scripts (ServerScriptService), src/client = LocalScripts \
(StarterPlayerScripts), src/shared = ModuleScripts (ReplicatedStorage), src/gui = ScreenGuis \
in Rojo .model.json format (StarterGui), notes.md = what the system does.

Naming rules (always follow):
1. Never add version suffixes, iteration markers or revision numbers to scripts, classes, \
nodes or files (no InventorySystemV3, PlayerMovement_New, Weapon_Final, Health_Updated).
2. Use clean, definitive, singular names (InventorySystem, PlayerMovement, Weapon).
3. Treat this code as the single source of truth for a clean production repository.
4. When changing existing code, refactor the existing name instead of making a V2 variant.

When you change a file, give the complete new file in one fenced code block so it can be \
applied directly. Keep explanations short and plain."""


def build_context(project: str | None, files: list[str], open_file: str | None,
                  open_text: str | None, notes: str | None) -> str:
    """What the assistant gets to see, trimmed to a sensible size."""
    parts = []
    if project:
        parts.append(f"Project: {project}")
    if files:
        parts.append("Files:\n" + "\n".join(f"- {f}" for f in files[:200]))
    if notes and notes.strip():
        parts.append("notes.md:\n" + notes.strip()[:4000])
    if open_file and open_text is not None:
        lang = "json" if open_file.endswith(".json") else \
            "markdown" if open_file.endswith(".md") else "lua"
        parts.append(f"Open file {open_file}:\n```{lang}\n{open_text}\n```")
    text = "\n\n".join(parts)
    if len(text) > MAX_CONTEXT_CHARS:
        text = text[:MAX_CONTEXT_CHARS] + "\n…(trimmed)"
    return text


def make_messages(history: list[dict], user_text: str, context: str) -> list[dict]:
    """Chat history plus the new message, with context attached to it."""
    msgs = [{"role": m["role"], "content": m["content"]} for m in history
            if m.get("role") in ("user", "assistant") and m.get("content")]
    content = user_text if not context else f"{user_text}\n\n<context>\n{context}\n</context>"
    msgs.append({"role": "user", "content": content})
    return msgs


CODE_RE = re.compile(r"```([\w+.-]*)[^\n]*\n(.*?)```", re.S)


def code_blocks(text: str) -> list[tuple[str, str]]:
    """[(language, code)] for every fenced block in a reply."""
    return [(lang.lower(), code.rstrip("\n") + "\n") for lang, code in CODE_RE.findall(text)]


# ---------------------------------------------------------------- streams

def parse_sse(lines):
    """Yield the JSON payload of each `data:` line of a server-sent stream."""
    for raw in lines:
        line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        try:
            yield json.loads(data)
        except ValueError:
            continue


def claude_text(events):
    for ev in events:
        t = ev.get("type")
        if t == "content_block_delta" and ev.get("delta", {}).get("type") == "text_delta":
            yield ev["delta"].get("text", "")
        elif t == "error":
            raise AssistantError("Claude: " + ev.get("error", {}).get("message", "error"))


def openai_text(events):
    for ev in events:
        if ev.get("error"):
            raise AssistantError("ChatGPT: " + str(ev["error"].get("message", "error")))
        for choice in ev.get("choices") or []:
            piece = (choice.get("delta") or {}).get("content")
            if piece:
                yield piece


def ollama_text(lines):
    for raw in lines:
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        if ev.get("error"):
            raise AssistantError("Ollama: " + str(ev["error"]))
        piece = (ev.get("message") or {}).get("content")
        if piece:
            yield piece
        if ev.get("done"):
            return


# ---------------------------------------------------------------- http

def _request(url, headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", "User-Agent": "Baseplate"}
    h.update(headers or {})
    return urllib.request.Request(url, data=data, headers=h,
                                  method="POST" if data else "GET")


def _open(req, provider: str):
    try:
        return urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        raise AssistantError(_explain(provider, e.code, _reason(e))) from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        if provider == "ollama":
            raise AssistantError(
                "Ollama isn't running. Install it from ollama.com, then run "
                "\"ollama pull qwen2.5-coder\" in a terminal and try again.") from None
        raise AssistantError(f"Couldn't reach {PROVIDERS[provider].company}. "
                             f"Check your internet connection. ({e})") from None


def _reason(e) -> str:
    try:
        body = json.loads(e.read() or b"{}")
    except (ValueError, OSError):
        return ""
    err = body.get("error")
    if isinstance(err, dict):
        return str(err.get("message", ""))[:300]
    return str(err or body.get("message") or "")[:300]


def _explain(provider: str, code: int, reason: str) -> str:
    p = PROVIDERS[provider]
    if code in (401, 403):
        return (f"{p.company} refused the API key ({reason or code}). "
                "Check it in Assistant settings.")
    if code == 404:
        return f"{p.short} doesn't know that model ({reason or 404}). Pick another in settings."
    if code == 429:
        return (f"{p.short} says slow down or add credit ({reason or 429}). "
                "API use is billed by the provider.")
    if code == 529 or code >= 500:
        return f"{p.short} is busy right now ({reason or code}). Try again in a moment."
    return f"{p.short} error {code}: {reason}"


def list_models(provider: str, ollama_url: str = DEFAULT_OLLAMA_URL) -> list[str]:
    if provider == "claude":
        key = _need_key(provider)
        with _open(_request("https://api.anthropic.com/v1/models?limit=100",
                            {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}),
                   provider) as r:
            return [m["id"] for m in json.load(r).get("data", [])]
    if provider == "openai":
        key = _need_key(provider)
        with _open(_request("https://api.openai.com/v1/models",
                            {"Authorization": f"Bearer {key}"}), provider) as r:
            ids = [m["id"] for m in json.load(r).get("data", [])]
        skip = ("audio", "realtime", "image", "tts", "transcribe", "embedding",
                "search", "moderation", "dall-e", "whisper")
        return sorted((i for i in ids if "gpt" in i and not any(s in i for s in skip)),
                      reverse=True)
    with _open(_request(ollama_url.rstrip("/") + "/api/tags"), provider) as r:
        return [m["name"] for m in json.load(r).get("models", [])]


def _need_key(provider):
    key = get_key(provider)
    if not key:
        raise AssistantError(f"Add your {PROVIDERS[provider].company} API key in "
                             "Assistant settings first.")
    return key


def stream_chat(provider: str, model: str, messages: list[dict], on_text,
                cancel: threading.Event | None = None,
                ollama_url: str = DEFAULT_OLLAMA_URL,
                system: str = SYSTEM_PROMPT) -> str:
    """Send the conversation; call on_text(piece) as the reply streams in.
    Returns the full reply. Stops early if `cancel` is set."""
    if not model:
        raise AssistantError("Pick a model in Assistant settings.")
    if provider == "claude":
        req = _request("https://api.anthropic.com/v1/messages",
                       {"x-api-key": _need_key(provider),
                        "anthropic-version": ANTHROPIC_VERSION},
                       {"model": model, "max_tokens": 8192, "system": system,
                        "messages": messages, "stream": True})
        pieces = lambda r: claude_text(parse_sse(r))  # noqa: E731
    elif provider == "openai":
        req = _request("https://api.openai.com/v1/chat/completions",
                       {"Authorization": f"Bearer {_need_key(provider)}"},
                       {"model": model, "stream": True,
                        "messages": [{"role": "system", "content": system}] + messages})
        pieces = lambda r: openai_text(parse_sse(r))  # noqa: E731
    elif provider == "ollama":
        req = _request(ollama_url.rstrip("/") + "/api/chat", None,
                       {"model": model, "stream": True,
                        "messages": [{"role": "system", "content": system}] + messages})
        pieces = ollama_text
    else:
        raise AssistantError("Unknown assistant.")
    out = []
    with _open(req, provider) as r:
        for piece in pieces(r):
            if cancel is not None and cancel.is_set():
                break
            out.append(piece)
            on_text(piece)
    return "".join(out)

"""The assistant panel docked on the right, and its settings window."""
from __future__ import annotations

import threading

from gi.repository import Adw, Gdk, GLib, Gtk, Pango

from . import assistant, core

SUGGESTIONS = [
    "Explain this script",
    "Find bugs in this file",
    "Add comments to this file",
    "Write a DataStore save system",
]


def _label(widget, text):
    widget.update_property([Gtk.AccessibleProperty.LABEL], [text])
    widget.set_tooltip_text(text)


class AssistantSettings(Adw.PreferencesDialog):
    """Pick Claude, ChatGPT or Ollama; add keys; choose a model."""

    def __init__(self, win, on_saved):
        super().__init__(title="Assistant settings", search_enabled=False)
        self.win, self.settings, self.on_saved = win, win.app.settings, on_saved
        page = Adw.PreferencesPage()
        self.add(page)

        group = Adw.PreferencesGroup(
            title="Assistant",
            description="Claude and ChatGPT run in the cloud and need an API key, billed "
                        "by Anthropic or OpenAI (a Claude.ai or ChatGPT subscription "
                        "doesn't include API use). Ollama is free and runs on this "
                        "computer; install it from ollama.com.")
        page.add(group)
        self.keys = list(assistant.PROVIDERS)
        self.provider_row = Adw.ComboRow(
            title="Use", model=Gtk.StringList.new([p.name for p in assistant.PROVIDERS.values()]))
        self.provider_row.set_selected(self.keys.index(self.provider))
        self.provider_row.connect("notify::selected", lambda *_: self._provider_changed())
        group.add(self.provider_row)

        self.key_row = Adw.PasswordEntryRow(title="API key")
        group.add(self.key_row)
        self.key_link = Adw.ActionRow(title="Get an API key", activatable=True)
        self.key_link.add_suffix(Gtk.Image(icon_name="adw-external-link-symbolic"))
        self.key_link.connect("activated", lambda *_: Gtk.UriLauncher.new(
            assistant.PROVIDERS[self.provider].key_url).launch(self.win, None, None, None))
        group.add(self.key_link)
        self.remove_key = Adw.ButtonRow(title="Remove saved key")
        self.remove_key.add_css_class("destructive-action")
        self.remove_key.connect("activated", lambda *_: self._remove_key())
        group.add(self.remove_key)

        self.url_row = Adw.EntryRow(title="Ollama address")
        self.url_row.set_text(self.settings.get("ollama_url") or assistant.DEFAULT_OLLAMA_URL)
        group.add(self.url_row)

        mgroup = Adw.PreferencesGroup(title="Model")
        page.add(mgroup)
        self.models = Gtk.StringList()
        self.model_row = Adw.ComboRow(title="Model", model=self.models, enable_search=True)
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", valign=Gtk.Align.CENTER)
        refresh.add_css_class("flat")
        _label(refresh, "Load the list of models")
        refresh.connect("clicked", lambda *_: self._load_models())
        self.model_row.add_suffix(refresh)
        mgroup.add(self.model_row)
        self.status = Gtk.Label(xalign=0, wrap=True, margin_top=6)
        self.status.add_css_class("bp-dim")
        mgroup.add(self.status)

        save = Adw.PreferencesGroup()
        btn = Gtk.Button(label="Save", halign=Gtk.Align.END)
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.connect("clicked", lambda *_: self._save())
        save.add(btn)
        page.add(save)
        self._provider_changed()

    @property
    def provider(self):
        if hasattr(self, "provider_row"):
            return self.keys[self.provider_row.get_selected()]
        return self.settings.get("ai_provider") or "ollama"

    def _provider_changed(self):
        p = assistant.PROVIDERS[self.provider]
        has_key = assistant.get_key(p.key) is not None
        self.key_row.set_visible(p.cloud)
        self.key_link.set_visible(p.cloud)
        self.remove_key.set_visible(p.cloud and has_key)
        self.key_row.set_title(f"{p.company} API key" + (" (saved)" if has_key else ""))
        self.key_row.set_text("")
        self.url_row.set_visible(not p.cloud)
        current = self.settings.get(f"ai_model_{p.key}") or p.default_model
        self._set_models([current] if current else [], current)
        self.status.set_label("Press ↻ to load the models you can use." if p.cloud or current
                              else "Press ↻ to list the models installed in Ollama.")

    def _set_models(self, names, selected=None):
        self.models.splice(0, self.models.get_n_items(), names)
        if selected in names:
            self.model_row.set_selected(names.index(selected))

    def _store_key(self):
        text = self.key_row.get_text().strip()
        if text:
            assistant.set_key(self.provider, text)
            self.key_row.set_text("")
            self._provider_changed()

    def _load_models(self):
        try:
            self._store_key()
        except core.BaseplateError as e:
            return self.status.set_label(str(e))
        provider, url = self.provider, self.url_row.get_text().strip()
        current = self._selected_model()
        self.status.set_label("Loading models…")

        def done(names, err):
            if err:
                return self.status.set_label(str(err))
            if not names:
                return self.status.set_label(
                    "No models found. For Ollama, run \"ollama pull qwen2.5-coder\" first.")
            self._set_models(names, current if current in names else names[0])
            self.status.set_label(f"{len(names)} models available.")
        self.win.in_background(lambda: assistant.list_models(provider, url), done)

    def _selected_model(self):
        item = self.model_row.get_selected_item()
        return item.get_string() if item else ""

    def _remove_key(self):
        assistant.set_key(self.provider, None)
        self._provider_changed()
        self.win.toast("API key removed.")

    def _save(self):
        try:
            self._store_key()
        except core.BaseplateError as e:
            return self.status.set_label(str(e))
        self.settings.set("ai_provider", self.provider)
        model = self._selected_model()
        if model:
            self.settings.set(f"ai_model_{self.provider}", model)
        url = self.url_row.get_text().strip()
        if url:
            self.settings.set("ollama_url", url)
        self.close()
        self.on_saved()


class AssistantPane(Gtk.Box):
    """Chat with the assistant about the open file and project."""

    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("bp-assistant")
        self.win = win
        self.history: list[dict] = []
        self.cancel: threading.Event | None = None
        self.busy = False

        head = Gtk.Box(spacing=6, margin_start=12, margin_end=8, margin_top=8, margin_bottom=6)
        title = Gtk.Label(label="Assistant", xalign=0)
        title.add_css_class("heading")
        head.append(title)
        self.who = Gtk.Label(xalign=0, hexpand=True, ellipsize=3)
        self.who.add_css_class("bp-chip")
        head.append(self.who)
        new = Gtk.Button(icon_name="list-add-symbolic")
        new.add_css_class("flat")
        _label(new, "New chat")
        new.connect("clicked", lambda *_: self.clear())
        head.append(new)
        gear = Gtk.Button(icon_name="emblem-system-symbolic")
        gear.add_css_class("flat")
        _label(gear, "Assistant settings")
        gear.connect("clicked", lambda *_: self.open_settings())
        head.append(gear)
        self.append(head)

        opts = Gtk.Box(spacing=12, margin_start=12, margin_end=12, margin_bottom=4)
        self.use_file = Gtk.CheckButton(label="Open file", active=True)
        _label(self.use_file, "Send the open file with your message")
        self.use_project = Gtk.CheckButton(label="File list & notes", active=True)
        _label(self.use_project, "Send the project's file names and notes.md")
        opts.append(Gtk.Label(label="Share:", css_classes=["bp-dim"]))
        opts.append(self.use_file)
        opts.append(self.use_project)
        self.append(opts)

        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                            margin_start=12, margin_end=12, margin_top=8, margin_bottom=8)
        self.scroll = Gtk.ScrolledWindow(child=self.list, vexpand=True,
                                         hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.append(self.scroll)
        self._show_empty()

        box = Gtk.Box(spacing=6, margin_start=10, margin_end=10, margin_bottom=10, margin_top=4)
        box.add_css_class("bp-input")
        self.input = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, accepts_tab=False,
                                  hexpand=True, top_margin=4, bottom_margin=4)
        _label(self.input, "Message the assistant. Enter sends, Shift+Enter adds a line.")
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.input.add_controller(keys)
        scroller = Gtk.ScrolledWindow(child=self.input, max_content_height=140,
                                      propagate_natural_height=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        box.append(scroller)
        self.send_btn = Gtk.Button(icon_name="go-up-symbolic", valign=Gtk.Align.END)
        self.send_btn.add_css_class("suggested-action")
        self.send_btn.add_css_class("circular")
        _label(self.send_btn, "Send (Enter)")
        self.send_btn.connect("clicked", lambda *_: self.send_or_stop())
        box.append(self.send_btn)
        self.append(box)
        self.refresh_who()

    # --- state
    @property
    def provider(self):
        return self.win.app.settings.get("ai_provider") or "ollama"

    @property
    def model(self):
        p = assistant.PROVIDERS[self.provider]
        return self.win.app.settings.get(f"ai_model_{p.key}") or p.default_model

    def refresh_who(self):
        p = assistant.PROVIDERS[self.provider]
        self.who.set_label(f"{p.short} · {self.model or 'pick a model'}")
        self.win.update_status()

    def open_settings(self):
        AssistantSettings(self.win, self.refresh_who).present(self.win)

    def focus_input(self):
        self.input.grab_focus()

    def clear(self):
        if self.busy:
            self.cancel.set()
        self.history.clear()
        child = self.list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.list.remove(child)
            child = nxt
        self._show_empty()

    # --- messages
    def _show_empty(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=24)
        hello = Gtk.Label(label="Ask about your scripts, or have the assistant write one.",
                          wrap=True, xalign=0)
        hello.add_css_class("bp-dim")
        box.append(hello)
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=2,
                           column_spacing=6, row_spacing=6)
        for s in SUGGESTIONS:
            b = Gtk.Button(label=s)
            b.add_css_class("bp-suggestion")
            b.connect("clicked", lambda _b, t=s: self.send(t))
            flow.append(b)
        box.append(flow)
        self.empty = box
        self.list.append(box)

    def _bubble(self, who: str, kind: str):
        if getattr(self, "empty", None) is not None:
            self.list.remove(self.empty)
            self.empty = None
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        name = Gtk.Label(label=who, xalign=0)
        name.add_css_class("bp-who")
        outer.append(name)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        body.add_css_class("bp-bubble")
        body.add_css_class(kind)
        outer.append(body)
        self.list.append(outer)
        return body

    @staticmethod
    def _text_label(text):
        lbl = Gtk.Label(label=text, wrap=True, xalign=0, selectable=True,
                        wrap_mode=Pango.WrapMode.WORD_CHAR)
        return lbl

    def _render(self, body, text):
        """Plain text plus code blocks with Apply / Insert / Copy buttons."""
        child = body.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            body.remove(child)
            child = nxt
        pos = 0
        for m in assistant.CODE_RE.finditer(text):
            before = text[pos:m.start()].strip()
            if before:
                body.append(self._text_label(before))
            body.append(self._code_block(m.group(1).lower(), m.group(2)))
            pos = m.end()
        rest = text[pos:].strip()
        if rest:
            body.append(self._text_label(rest))

    def _code_block(self, lang, code):
        code = code.rstrip("\n") + "\n"
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        lbl = Gtk.Label(label=code.rstrip("\n"), xalign=0, selectable=True, wrap=False)
        lbl.add_css_class("bp-code")
        scroller = Gtk.ScrolledWindow(child=lbl, vscrollbar_policy=Gtk.PolicyType.NEVER,
                                      propagate_natural_height=True)
        box.append(scroller)
        bar = Gtk.Box(spacing=4)
        bar.add_css_class("bp-codebar")
        for text, tip, fn in (
                ("Apply to file", "Replace the open file with this code (undo with Ctrl+Z)",
                 lambda: self.win.apply_code(code)),
                ("Insert", "Insert at the cursor", lambda: self.win.insert_code(code)),
                ("New script…", "Save this as a new script in the project",
                 lambda: self.win.new_script(code)),
                ("Copy", "Copy to the clipboard", lambda: self._copy(code))):
            b = Gtk.Button(label=text)
            b.add_css_class("flat")
            _label(b, tip)
            b.connect("clicked", lambda _b, f=fn: f())
            bar.append(b)
        if lang:
            tag = Gtk.Label(label=lang, hexpand=True, xalign=1)
            tag.add_css_class("bp-dim")
            bar.append(tag)
        box.append(bar)
        return box

    def _copy(self, text):
        Gdk.Display.get_default().get_clipboard().set(text)
        self.win.toast("Copied.")

    def _scroll_end(self):
        adj = self.scroll.get_vadjustment()
        GLib.idle_add(lambda: adj.set_value(adj.get_upper()) or False)

    # --- sending
    def _key(self, _c, keyval, _code, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and \
                not state & Gdk.ModifierType.SHIFT_MASK:
            self.send_or_stop()
            return True
        return False

    def send_or_stop(self):
        if self.busy:
            self.cancel.set()
            return
        buf = self.input.get_buffer()
        text = buf.get_text(*buf.get_bounds(), False).strip()
        if text:
            self.send(text)

    def send(self, text):
        p = assistant.PROVIDERS[self.provider]
        if p.cloud and not assistant.get_key(p.key):
            self.win.toast(f"Add your {p.company} API key first, or switch to Ollama.")
            return self.open_settings()
        if p.cloud and not self.win.app.settings.get(f"ai_ok_{p.key}"):
            return self._ask_cloud_ok(p, text)
        self._send(text)

    def _ask_cloud_ok(self, p, text):
        """Before the first message to a cloud AI: say exactly what is sent."""
        dlg = Adw.AlertDialog(
            heading=f"Send to {p.company}?",
            body=f"Your messages go to {p.company}'s servers, along with what you "
                 "chose to share (the open file, the project's file names and "
                 f"notes.md). {p.company} bills your API account for each message. "
                 "Your projects are not uploaded otherwise. Ollama keeps everything "
                 "on this computer instead.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("ok", "Send")
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("cancel")
        dlg.set_close_response("cancel")

        def done(_d, r):
            if r == "ok":
                self.win.app.settings.set(f"ai_ok_{p.key}", True)
                self._send(text)
        dlg.connect("response", done)
        dlg.present(self.win)

    def _send(self, text):
        self.input.get_buffer().set_text("")
        ctx = self.win.assistant_context(self.use_file.get_active(),
                                         self.use_project.get_active())
        messages = assistant.make_messages(self.history, text, ctx)
        self._render(self._bubble("You", "user"), text)
        body = self._bubble(assistant.PROVIDERS[self.provider].short, "ai")
        live = self._text_label("…")
        body.append(live)
        self._scroll_end()
        self.history.append({"role": "user", "content": text})

        provider, model = self.provider, self.model
        url = self.win.app.settings.get("ollama_url") or assistant.DEFAULT_OLLAMA_URL
        self.cancel, self.busy = threading.Event(), True
        self.send_btn.set_icon_name("media-playback-stop-symbolic")
        _label(self.send_btn, "Stop")
        shown = []

        def piece(t):
            shown.append(t)
            GLib.idle_add(lambda s="".join(shown): (live.set_label(s), self._scroll_end())
                          and False)

        def work():
            return assistant.stream_chat(provider, model, messages, piece, self.cancel,
                                         ollama_url=url)

        def done(reply, err):
            self.busy = False
            self.send_btn.set_icon_name("go-up-symbolic")
            _label(self.send_btn, "Send (Enter)")
            if err:
                body.remove_css_class("ai")
                body.add_css_class("err")
                live.set_label(str(err))
                self.history.pop()
                self.win.sounds.play("error")
                return
            reply = reply or "".join(shown)
            if self.cancel.is_set():
                reply += "\n\n(stopped)"
            self.history.append({"role": "assistant", "content": reply})
            self._render(body, reply)
            self._scroll_end()
            self.win.sounds.play("success")
        self.win.in_background(work, done)

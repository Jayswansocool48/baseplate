"""Roblox Vault GTK4 / libadwaita interface."""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

try:
    gi.require_version("GtkSource", "5")
    from gi.repository import GtkSource  # noqa: E402
except (ValueError, ImportError):
    GtkSource = None

try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit  # noqa: E402
except (ValueError, ImportError):
    WebKit = None

from . import core, figma, preview  # noqa: E402
from .sounds import Sounds  # noqa: E402

LEGAL_DIR = Path(__file__).parent / "legal"
BUSINESS_FILE = Path(__file__).parent / "business.json"
LEGAL_PAGES = [
    ("privacy", "Privacy Policy"),
    ("terms", "Terms of Service"),
    ("refund", "Refund Policy"),
    ("cookies", "Cookie Policy"),
    ("third_party", "Third-Party Software & Licenses"),
    ("accessibility", "Accessibility"),
]


def label(widget: Gtk.Widget, text: str):
    """Give a widget a screen-reader name (the 'alt text' for icons)."""
    widget.update_property([Gtk.AccessibleProperty.LABEL], [text])
    widget.set_tooltip_text(text)


def business() -> dict:
    try:
        return json.loads(BUSINESS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def read_legal(key: str) -> str:
    text = (LEGAL_DIR / f"{key}.md").read_text()
    b = business()
    country = f" ({b['country']})" if b.get("country") else ""
    values = {
        "owner_name": (b.get("owner_name") or "the developer") + country,
        "contact": b.get("contact") or "the project's GitHub Issues page",
        "website": b.get("website") or "the project's GitHub page",
    }
    for k, v in values.items():
        text = text.replace("{" + k + "}", v)
    return text


def open_in_browser(window, uri):
    Gtk.UriLauncher.new(uri).launch(window, None, None, None)


# ---------------------------------------------------------------- dialogs

def ask_text(parent, heading, body, placeholder, on_ok, extra=None):
    dlg = Adw.MessageDialog(transient_for=parent, heading=heading, body=body)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    entry = Gtk.Entry(placeholder_text=placeholder, activates_default=True)
    label(entry, placeholder)
    box.append(entry)
    drop = None
    if extra:
        drop = Gtk.DropDown.new_from_strings(extra[1])
        label(drop, extra[0])
        box.append(Gtk.Label(label=extra[0], xalign=0))
        box.append(drop)
    dlg.set_extra_child(box)
    dlg.add_response("cancel", "Cancel")
    dlg.add_response("ok", "Create")
    dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
    dlg.set_default_response("ok")
    dlg.set_close_response("cancel")

    def done(_d, resp):
        if resp == "ok":
            on_ok(entry.get_text(), extra[1][drop.get_selected()] if drop else None)
    dlg.connect("response", done)
    dlg.present()


def confirm(parent, heading, body, action_label, on_yes, destructive=True):
    dlg = Adw.MessageDialog(transient_for=parent, heading=heading, body=body)
    dlg.add_response("cancel", "Cancel")
    dlg.add_response("yes", action_label)
    dlg.set_response_appearance(
        "yes", Adw.ResponseAppearance.DESTRUCTIVE if destructive
        else Adw.ResponseAppearance.SUGGESTED)
    dlg.set_default_response("cancel")  # safe choice is the default
    dlg.set_close_response("cancel")
    dlg.connect("response", lambda _d, r: r == "yes" and on_yes())
    dlg.present()


class LegalWindow(Adw.Window):
    def __init__(self, parent, start="privacy"):
        super().__init__(transient_for=parent, modal=True, title="Legal",
                         default_width=720, default_height=560)
        stack = Gtk.Stack()
        for key, title in LEGAL_PAGES:
            view = Gtk.TextView(editable=False, cursor_visible=False,
                                wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                left_margin=18, right_margin=18,
                                top_margin=12, bottom_margin=12)
            view.get_buffer().set_text(read_legal(key))
            label(view, title)
            stack.add_titled(Gtk.ScrolledWindow(child=view, hexpand=True), key, title)
        stack.set_visible_child_name(start)
        box = Gtk.Box()
        box.append(Gtk.StackSidebar(stack=stack))
        box.append(stack)
        tv = Adw.ToolbarView(content=box)
        tv.add_top_bar(Adw.HeaderBar())
        self.set_content(tv)


class ConsentWindow(Adw.Window):
    """First-run consent. Boxes start unticked; Quit is as easy as Continue."""

    def __init__(self, app, on_accept):
        super().__init__(application=app, title="Welcome to Roblox Vault",
                         default_width=560, resizable=False)
        self.on_accept = on_accept
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=24, margin_bottom=24, margin_start=24, margin_end=24)
        title = Gtk.Label(label="Before you start", xalign=0)
        title.add_css_class("title-2")
        box.append(title)
        box.append(Gtk.Label(wrap=True, xalign=0, label=(
            "Roblox Vault stores your scripts and GUIs only on this computer. "
            "It has no account, no ads, no tracking and no payments. The app "
            "itself stays offline; only the optional Figma tab goes online, and "
            "only after you open it. Rojo sync only listens on this computer.")))
        self.checks = []
        for text, page in (("I have read and agree to the Terms of Service", "terms"),
                           ("I have read the Privacy Policy", "privacy"),
                           ("I am 13 or older, or my parent or guardian has "
                            "said I can use this app", None)):
            row = Gtk.Box(spacing=8)
            chk = Gtk.CheckButton(label=text, active=False)
            chk.connect("toggled", self._update)
            row.append(chk)
            if page:
                btn = Gtk.Button(label="Read", valign=Gtk.Align.CENTER)
                label(btn, "Read the " + ("Terms of Service" if page == "terms" else "Privacy Policy"))
                btn.connect("clicked", lambda _b, p=page: LegalWindow(self, p).present())
                row.append(btn)
            self.checks.append(chk)
            box.append(row)
        buttons = Gtk.Box(spacing=12, halign=Gtk.Align.END)
        quit_btn = Gtk.Button(label="Quit")
        quit_btn.connect("clicked", lambda _b: app.quit())
        self.ok = Gtk.Button(label="Continue", sensitive=False)
        self.ok.add_css_class("suggested-action")
        self.ok.connect("clicked", self._accept)
        buttons.append(quit_btn)
        buttons.append(self.ok)
        box.append(buttons)
        self.set_content(box)

    def _update(self, *_):
        self.ok.set_sensitive(all(c.get_active() for c in self.checks))

    def _accept(self, *_):
        self.on_accept(*(c.get_active() for c in self.checks))
        self.close()


# ---------------------------------------------------------------- preview pane

class PreviewPane(Gtk.Box):
    """Draws the open GUI on a pretend Roblox screen, with a layers list."""

    def __init__(self, on_click):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_click = on_click
        self.items, self.notes = [], []
        self.model = None
        self.hover = self.pressed = None
        self.screen = preview.DEVICES[0][1:]
        self._fit = (1.0, 0.0, 0.0)

        bar = Gtk.Box(spacing=8, margin_start=8, margin_end=8, margin_top=6, margin_bottom=6)
        self.device = Gtk.DropDown.new_from_strings([d[0] for d in preview.DEVICES])
        label(self.device, "Screen size")
        self.device.connect("notify::selected", self._device_changed)
        bar.append(Gtk.Label(label="Screen"))
        bar.append(self.device)
        self.status = Gtk.Label(xalign=0, hexpand=True, ellipsize=3)
        self.status.add_css_class("dim-label")
        bar.append(self.status)
        self.append(bar)

        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True, focusable=True)
        label(self.area, "GUI preview. The layers list beside it describes every element.")
        self.area.set_draw_func(self._draw)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._motion)
        motion.connect("leave", lambda *_: self._set_hover(None))
        self.area.add_controller(motion)
        click = Gtk.GestureClick()
        click.connect("pressed", self._pressed)
        click.connect("released", self._released)
        self.area.add_controller(click)

        self.layers = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        label(self.layers, "Layers in this GUI")
        self.layers.connect("row-selected", self._layer_selected)
        side = Gtk.ScrolledWindow(child=self.layers, min_content_width=220,
                                  hscrollbar_policy=Gtk.PolicyType.NEVER)
        body = Gtk.Paned(start_child=self.area, end_child=side,
                         resize_end_child=False, shrink_end_child=False)
        self.empty = Adw.StatusPage(icon_name="view-grid-symbolic",
                                    title="Nothing to preview",
                                    description="Open a GUI (in the gui folder) or "
                                                "import one from the Figma tab.")
        self.stack = Gtk.Stack()
        self.stack.add_named(self.empty, "empty")
        self.stack.add_named(body, "preview")
        self.stack.set_vexpand(True)
        self.append(self.stack)

    def set_text(self, text: str | None):
        if text is None:
            self.model = None
            self.stack.set_visible_child_name("empty")
            return
        try:
            self.model = json.loads(text)
        except json.JSONDecodeError as e:
            self.status.set_label(f"Can't preview: JSON error on line {e.lineno}")
            return  # keep showing the last good version
        self.stack.set_visible_child_name("preview")
        self._relayout()

    def _device_changed(self, *_):
        self.screen = preview.DEVICES[self.device.get_selected()][1:]
        self._relayout()

    def _relayout(self):
        if self.model is None:
            return
        sw, sh = self.screen
        self.items, self.notes = preview.layout(self.model, sw, sh)
        self.hover = self.pressed = None
        self.status.set_label(" ".join(self.notes) or
                              f"{len(self.items)} elements. Hover to inspect, click buttons to test.")
        self.layers.remove_all()
        for it in self.items:
            row = Gtk.ListBoxRow()
            text = f"{'  ' * it.depth}{it.name}  ({it.cls})"
            if it.text:
                text += f' "{it.text[:30]}"'
            row.set_child(Gtk.Label(label=text, xalign=0, margin_start=6,
                                    margin_top=2, margin_bottom=2, ellipsize=3))
            row.item = it
            self.layers.append(row)
        self.area.queue_draw()

    def _draw(self, _area, cr, w, h):
        if not self.items and self.model is None:
            return
        sw, sh = self.screen
        s = min(w / sw, h / sh) * 0.96
        ox, oy = (w - sw * s) / 2, (h - sh * s) / 2
        self._fit = (s, ox, oy)
        cr.translate(ox, oy)
        cr.scale(s, s)
        cr.rectangle(0, 0, sw, sh)
        cr.clip()
        top = not preview.prop((self.model or {}).get("Properties") or {}, "IgnoreGuiInset", False)
        preview.draw(cr, self.items, sw, sh, top, self.hover, self.pressed)

    def _to_screen(self, x, y):
        s, ox, oy = self._fit
        return (x - ox) / s, (y - oy) / s

    def _set_hover(self, it):
        if it is not self.hover:
            self.hover = it
            if it:
                self.status.set_label(f"{it.path.lstrip('/')}  ·  {it.cls}  ·  "
                                      f"{round(it.w)}×{round(it.h)} px")
            self.area.queue_draw()

    def _motion(self, _c, x, y):
        self._set_hover(preview.hit(self.items, *self._to_screen(x, y)))

    def _pressed(self, _g, _n, x, y):
        it = preview.hit(self.items, *self._to_screen(x, y))
        self.pressed = it if it and it.clickable else None
        self.area.queue_draw()

    def _released(self, _g, _n, x, y):
        it = preview.hit(self.items, *self._to_screen(x, y))
        if self.pressed and it is self.pressed:
            self.on_click(it)
        self.pressed = None
        self.area.queue_draw()

    def _layer_selected(self, _lb, row):
        if row:
            self._set_hover(row.item)


# ---------------------------------------------------------------- figma pane

class FigmaPane(Gtk.Box):
    """figma.com inside the app, plus Import / Connect controls."""

    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.view = None
        self._clip_handler = None

        self.banner = Adw.Banner(button_label="Cancel")
        self.banner.connect("button-clicked", lambda *_: self.stop_connect())
        self.append(self.banner)

        bar = Gtk.Box(spacing=6, margin_start=8, margin_end=8, margin_top=6, margin_bottom=6)
        self.nav = []
        for icon, text, fn in (("go-previous-symbolic", "Back", lambda: self.view.go_back()),
                               ("go-next-symbolic", "Forward", lambda: self.view.go_forward()),
                               ("view-refresh-symbolic", "Reload Figma page", lambda: self.view.reload()),
                               ("go-home-symbolic", "Figma home", lambda: self.view.load_uri(figma.HOME_URL))):
            b = Gtk.Button(icon_name=icon, sensitive=False)
            label(b, text)
            b.connect("clicked", lambda _b, f=fn: f())
            bar.append(b)
            self.nav.append(b)
        self.where = Gtk.Label(xalign=0, hexpand=True, ellipsize=3)
        self.where.add_css_class("dim-label")
        bar.append(self.where)
        self.sizing = Gtk.DropDown.new_from_strings(["Pixel size", "Scale to screen"])
        self.sizing.set_selected(1 if win.app.settings.get("figma_scale") else 0)
        self.sizing.connect("notify::selected", lambda *_: win.app.settings.set(
            "figma_scale", self.sizing.get_selected() == 1))
        label(self.sizing, "How imported GUIs are sized")
        bar.append(self.sizing)
        self.import_btn = Gtk.Button(label="Import selected frame", sensitive=False)
        self.import_btn.add_css_class("suggested-action")
        self.import_btn.set_action_name("win.figma-import")
        label(self.import_btn, "Import the frame selected in Figma as a Roblox GUI (Ctrl+I)")
        bar.append(self.import_btn)
        self.account = Gtk.MenuButton()
        label(self.account, "Figma connection")
        bar.append(self.account)
        self.append(bar)

        self.stack = Gtk.Stack(vexpand=True)
        self.append(self.stack)
        if WebKit is None:
            page = Adw.StatusPage(
                icon_name="dialog-warning-symbolic", title="Figma tab needs WebKit",
                description="Run install.sh again (it adds gir1.2-webkit-6.0), "
                            "then restart the app.")
            self.stack.add_named(page, "missing")
        else:
            start = Gtk.Button(label="Open Figma", halign=Gtk.Align.CENTER)
            start.add_css_class("pill")
            start.add_css_class("suggested-action")
            start.connect("clicked", lambda *_: self.start_web())
            page = Adw.StatusPage(
                icon_name="applications-graphics-symbolic", title="Design in Figma, right here",
                description="This tab is a small web browser for figma.com. Sign in "
                            "with your Figma account, design a frame, select it and "
                            "press Import. Figma (not this app) stores its own sign-in "
                            "cookies for this tab; Menu → Figma → Sign out clears them.",
                child=start)
            self.stack.add_named(page, "intro")
            if win.app.settings.get("figma_tab_opened"):
                GLib.idle_add(self.start_web)
        self.update_account()

    # --- web view
    def start_web(self):
        if self.view:
            return
        self.win.app.settings.set("figma_tab_opened", True)
        d = figma.web_data_dir()
        d.mkdir(parents=True, exist_ok=True)
        self.session = WebKit.NetworkSession.new(str(d / "data"), str(d / "cache"))
        self.session.get_cookie_manager().set_persistent_storage(
            str(d / "cookies.sqlite"), WebKit.CookiePersistentStorage.SQLITE)
        self.view = WebKit.WebView(network_session=self.session, vexpand=True)
        label(self.view, "Figma")
        self.view.connect("notify::uri", self._uri_changed)
        self.view.connect("create", self._new_window)
        self.stack.add_named(self.view, "web")
        self.stack.set_visible_child_name("web")
        for b in self.nav:
            b.set_sensitive(True)
        self.view.load_uri(figma.HOME_URL)

    def _new_window(self, _view, action):
        """Pop-ups (help pages, other sites) open in the normal browser."""
        uri = action.get_request().get_uri()
        if uri and figma.parse_url(uri)[0]:
            self.view.load_uri(uri)
        elif uri:
            open_in_browser(self.win, uri)
        return None

    def _uri_changed(self, *_):
        key, node = figma.parse_url(self.uri)
        self.import_btn.set_sensitive(bool(key))
        title = self.view.get_title() or ""
        self.where.set_label(
            f"{title} · frame selected" if key and node else
            f"{title} · select a frame to import" if key else
            "Open a design file to import from it")

    @property
    def uri(self) -> str:
        return self.view.get_uri() if self.view else ""

    # --- connection (no pasting: the token is picked up when you press Copy)
    def update_account(self):
        menu = Gio.Menu()
        if figma.get_token():
            self.account.set_label("Connected")
            menu.append("Reconnect", "win.figma-connect")
        else:
            self.account.set_label("Connect Figma")
            menu.append("Connect Figma", "win.figma-connect")
        menu.append("Sign out of Figma", "win.figma-signout")
        menu.append("Open in web browser", "win.figma-browser")
        self.account.set_menu_model(menu)

    def start_connect(self, then=None):
        if WebKit is None:
            return self.win.toast("The Figma tab needs WebKit. Run install.sh again.")
        self._then = then
        self.win.show_page("figma")
        self.start_web()
        self.view.load_uri(figma.HOME_URL)
        self.banner.set_title(
            "Connecting: in Figma click your name → Settings → Security → "
            "Generate new token (File content: read-only), then press Copy. "
            "The app picks it up by itself.")
        self.banner.set_revealed(True)
        cb = self.win.get_display().get_clipboard()
        if self._clip_handler is None:
            self._clip_handler = cb.connect("changed", self._clipboard_changed)

    def stop_connect(self):
        self.banner.set_revealed(False)
        if self._clip_handler is not None:
            self.win.get_display().get_clipboard().disconnect(self._clip_handler)
            self._clip_handler = None

    def _clipboard_changed(self, cb):
        """Only runs while the Connecting banner is showing. Only a Figma token
        (figd_...) is kept; anything else on the clipboard is ignored."""
        def got(cb, res):
            try:
                text = cb.read_text_finish(res)
            except GLib.Error:
                return
            token = figma.find_token(text)
            if not token:
                return
            self.stop_connect()
            # Saved locally only. No test request: checks like Figma's /me need
            # extra token permissions, and every request counts toward Figma's
            # monthly limit. The first Import shows whether the token works.
            try:
                figma.set_token(token)
            except core.VaultError as e:
                return self.win.toast(str(e), "error")
            try:
                cb.set_content(None)  # don't leave the token on the clipboard
            except Exception:  # noqa: BLE001
                pass
            self.update_account()
            self.win.toast("Figma connected.", "success")
            then, self._then = self._then, None
            if then:
                then()
        cb.read_text_async(None, got)

    def sign_out(self):
        def finish(*_a):
            figma.disconnect(remove_web=False)
            self.update_account()
            if self.view:
                self.view.load_uri(figma.HOME_URL)
            self.win.toast("Signed out of Figma and cleared its cookies.")
        if self.view:
            self.session.get_website_data_manager().clear(
                WebKit.WebsiteDataTypes.ALL, 0, None, finish)
        else:
            figma.disconnect()
            finish()


# ---------------------------------------------------------------- main window

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=core.APP_NAME,
                         default_width=1280, default_height=800)
        self.app = app
        self.sounds = Sounds(app.settings)
        self.project: str | None = None
        self.file: str | None = None
        self.dirty = False
        self._preview_timer = 0
        self.rojo = core.RojoServer(
            on_output=lambda l: GLib.idle_add(self._log, l),
            on_exit=lambda c: GLib.idle_add(self._rojo_exited, c))

        self.toasts = Adw.ToastOverlay()
        header = Adw.HeaderBar()

        def hbtn(icon, text, action):
            b = Gtk.Button(icon_name=icon, action_name=action)
            label(b, text)
            return b

        header.pack_start(hbtn("folder-new-symbolic", "New project (Ctrl+Shift+N)", "win.new-project"))
        header.pack_start(hbtn("document-new-symbolic", "New script (Ctrl+N)", "win.new-script"))
        header.pack_start(hbtn("view-grid-symbolic", "New GUI (Ctrl+G)", "win.new-gui"))
        header.pack_start(hbtn("document-save-symbolic", "Save (Ctrl+S)", "win.save"))

        self.sync_btn = Gtk.ToggleButton(icon_name="emblem-synchronizing-symbolic")
        label(self.sync_btn, "Sync with Roblox Studio (Ctrl+R)")
        self.sync_btn.connect("toggled", self._toggle_sync)
        header.pack_end(self._menu_button())
        header.pack_end(hbtn("document-send-symbolic", "Build place file (Ctrl+B)", "win.build"))
        header.pack_end(self.sync_btn)
        header.pack_end(hbtn("view-refresh-symbolic", "Update GUIs from Figma (Ctrl+Shift+R)", "win.figma-refresh"))

        # sidebar
        self.projects = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        label(self.projects, "Projects")
        self.projects.connect("row-selected", self._project_selected)
        self.files = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        label(self.files, "Files in project")
        self.files.connect("row-selected", self._file_selected)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                       margin_top=6, margin_start=6, margin_end=6, margin_bottom=6)
        for title, lst in (("Projects", self.projects), ("Files", self.files)):
            h = Gtk.Label(label=title, xalign=0)
            h.add_css_class("heading")
            side.append(h)
            side.append(Gtk.ScrolledWindow(child=lst, vexpand=True,
                                           hscrollbar_policy=Gtk.PolicyType.NEVER))

        # code editor
        if GtkSource:
            self.buffer = GtkSource.Buffer()
            self.buffer.set_language(GtkSource.LanguageManager.get_default().get_language("lua"))
            self._sm = GtkSource.StyleSchemeManager.get_default()
            Adw.StyleManager.get_default().connect("notify::dark", self._scheme)
            self._scheme()
            self.editor = GtkSource.View(buffer=self.buffer, monospace=True,
                                         show_line_numbers=True, auto_indent=True,
                                         tab_width=4, highlight_current_line=True)
        else:
            self.buffer = Gtk.TextBuffer()
            self.editor = Gtk.TextView(buffer=self.buffer, monospace=True)
        label(self.editor, "Code editor")
        self.editor.set_sensitive(False)
        self.buffer.connect("changed", self._changed)
        self.file_title = Gtk.Label(label="Pick or create a project", xalign=0,
                                    margin_start=8, margin_top=4, margin_bottom=4)
        self.file_title.add_css_class("dim-label")

        # tabs: Code / Preview / Figma
        self.preview = PreviewPane(self._preview_clicked)
        self.figma = FigmaPane(self)
        self.pages = Adw.ViewStack(vexpand=True)
        self.pages.add_titled_with_icon(Gtk.ScrolledWindow(child=self.editor), "code",
                                        "Code", "text-x-generic-symbolic")
        self.pages.add_titled_with_icon(self.preview, "preview", "Preview",
                                        "view-reveal-symbolic")
        self.pages.add_titled_with_icon(self.figma, "figma", "Figma",
                                        "applications-graphics-symbolic")
        header.set_title_widget(Adw.ViewSwitcher(stack=self.pages,
                                                 policy=Adw.ViewSwitcherPolicy.WIDE))

        # sync log
        self.log_view = Gtk.TextView(editable=False, monospace=True, cursor_visible=False)
        label(self.log_view, "Sync and Figma log")
        log_scroll = Gtk.ScrolledWindow(child=self.log_view, min_content_height=90)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right.append(self.file_title)
        right.append(self.pages)
        right.append(Gtk.Separator())
        right.append(log_scroll)

        paned = Gtk.Paned(start_child=side, end_child=right, position=250,
                          shrink_start_child=False)
        tv = Adw.ToolbarView(content=paned)
        tv.add_top_bar(header)
        self.toasts.set_child(tv)
        self.set_content(self.toasts)

        self._actions()
        self.connect("close-request", self._on_close)
        self._reload_projects()

    # --- setup helpers
    def _menu_button(self):
        menu = Gio.Menu()
        sec = Gio.Menu()
        sec.append("Delete current file", "win.delete-file")
        sec.append("Delete current project", "win.delete-project")
        sec.append("Open project folder", "win.open-folder")
        menu.append_section(None, sec)
        fig = Gio.Menu()
        fig.append("Import selected Figma frame", "win.figma-import")
        fig.append("Update GUIs from Figma", "win.figma-refresh")
        fig.append("Connect Figma", "win.figma-connect")
        fig.append("Sign out of Figma", "win.figma-signout")
        menu.append_section("Figma", fig)
        sec2 = Gio.Menu()
        sec2.append("Setting up sync", "win.help-sync")
        sec2.append("Keyboard shortcuts", "win.shortcuts")
        sec2.append("Legal & privacy", "win.legal")
        sec2.append("Sound effects", "win.sounds")
        sec2.append("About Roblox Vault", "win.about")
        menu.append_section(None, sec2)
        sec3 = Gio.Menu()
        sec3.append("Delete all my data…", "win.delete-all")
        sec3.append("Uninstall Roblox Vault…", "win.uninstall")
        menu.append_section(None, sec3)
        b = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        label(b, "Main menu (F10)")
        return b

    def _actions(self):
        table = {
            "new-project": (self.new_project, ["<Ctrl><Shift>n"]),
            "new-script": (self.new_script, ["<Ctrl>n"]),
            "new-gui": (self.new_gui, ["<Ctrl>g"]),
            "save": (self.save, ["<Ctrl>s"]),
            "build": (self.build, ["<Ctrl>b"]),
            "sync": (lambda: self.sync_btn.set_active(not self.sync_btn.get_active()), ["<Ctrl>r"]),
            "page-code": (lambda: self.show_page("code"), ["<Alt>1"]),
            "page-preview": (lambda: self.show_page("preview"), ["<Alt>2"]),
            "page-figma": (lambda: self.show_page("figma"), ["<Alt>3"]),
            "figma-import": (lambda: self.figma_import(), ["<Ctrl>i"]),
            "figma-refresh": (self.figma_refresh, ["<Ctrl><Shift>r"]),
            "figma-connect": (lambda: self.figma.start_connect(), []),
            "figma-signout": (self.figma_signout, []),
            "figma-browser": (lambda: open_in_browser(self, self.figma.uri or figma.HOME_URL), []),
            "delete-file": (self.delete_file, []),
            "delete-project": (self.delete_project, []),
            "open-folder": (self.open_folder, []),
            "help-sync": (self.help_sync, []),
            "shortcuts": (self.shortcuts, ["<Ctrl>question"]),
            "legal": (lambda: LegalWindow(self).present(), []),
            "delete-all": (self.delete_all, []),
            "uninstall": (self.uninstall, []),
            "about": (self.about, []),
        }
        for name, (fn, accels) in table.items():
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda *_a, f=fn: f())
            self.add_action(act)
            if accels:
                self.app.set_accels_for_action(f"win.{name}", accels)
        # on/off checkbox in the menu
        snd = Gio.SimpleAction.new_stateful(
            "sounds", None, GLib.Variant.new_boolean(self.sounds.enabled))

        def toggle(action, _p):
            on = not action.get_state().get_boolean()
            action.set_state(GLib.Variant.new_boolean(on))
            self.sounds.set_enabled(on)
            self.toast("Sound effects on." if on else "Sound effects off.",
                       "success" if on else None)
        snd.connect("activate", toggle)
        self.add_action(snd)

    def _scheme(self, *_):
        dark = Adw.StyleManager.get_default().get_dark()
        s = self._sm.get_scheme("Adwaita-dark" if dark else "Adwaita")
        if s:
            self.buffer.set_style_scheme(s)

    def show_page(self, name):
        self.pages.set_visible_child_name(name)
        if name == "figma" and WebKit is not None and self.app.settings.get("figma_tab_opened"):
            self.figma.start_web()

    def toast(self, text, sound=None):
        """Show a message. A sound, if any, only ever accompanies the text."""
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(str(text)), timeout=5))
        if sound:
            self.sounds.play(sound)

    def guard(self, fn, *args):
        """Run fn; show errors as a toast. Returns fn's result, or None on error."""
        try:
            return fn(*args)
        except core.VaultError as e:
            self.toast(str(e), "error")
        except OSError as e:
            self.toast(f"File error: {e.strerror or e}", "error")

    def attempt(self, fn, *args) -> bool:
        """Like guard, for functions that return nothing: True if it worked."""
        try:
            fn(*args)
            return True
        except core.VaultError as e:
            self.toast(str(e), "error")
        except OSError as e:
            self.toast(f"File error: {e.strerror or e}", "error")
        return False

    def in_background(self, work, on_done):
        """Run network work off the UI thread so the window never freezes.
        on_done(result, error) runs back on the UI thread; error is an exception."""
        def run():
            try:
                result, err = work(), None
            except core.VaultError as e:
                result, err = None, e
            except Exception as e:  # noqa: BLE001 - never crash on odd Figma data
                result, err = None, core.VaultError(f"Unexpected Figma data: {e}")
            GLib.idle_add(on_done, result, err)
        threading.Thread(target=run, daemon=True).start()

    # --- lists
    @staticmethod
    def _row(text, data):
        row = Gtk.ListBoxRow()
        row.set_child(Gtk.Label(label=text, xalign=0, margin_start=6,
                                margin_top=4, margin_bottom=4, ellipsize=3))
        row.data = data
        label(row, text)
        return row

    def _reload_projects(self, select=None):
        self.projects.remove_all()
        for name in core.list_projects():
            row = self._row(name, name)
            self.projects.append(row)
            if name == select:
                self.projects.select_row(row)

    def _reload_files(self, select=None):
        self.files.remove_all()
        if not self.project:
            return
        linked = figma.linked_guis(self.project)
        for rel in core.list_files(self.project):
            pretty = rel.removeprefix("src/")
            if rel.startswith("src/gui/") and Path(rel).name.removesuffix(".model.json") in linked:
                pretty += "  (Figma)"
            row = self._row(pretty, rel)
            self.files.append(row)
            if rel == select:
                self.files.select_row(row)

    def _project_selected(self, _lb, row):
        if row:
            self._leave_file(lambda: self._open_project(row.data))

    def _open_project(self, name):
        self.project, self.file = name, None
        self._set_editor(None, "")
        self._reload_files(select="notes.md")

    def _file_selected(self, _lb, row):
        if row and row.data != self.file:
            self._leave_file(lambda: self._open_file(row.data))

    def _open_file(self, rel):
        text = self.guard(core.read_file, self.project, rel)
        if text is not None:
            self.file = rel
            self._set_editor(rel, text)

    def _is_gui(self, rel):
        return bool(rel) and rel.endswith(".model.json")

    def _set_editor(self, rel, text):
        self.buffer.set_text(text)
        self.dirty = False
        self.editor.set_sensitive(rel is not None)
        self.file_title.set_label(f"{self.project} / {rel}" if rel else
                                  (self.project or "Pick or create a project"))
        self.preview.set_text(text if self._is_gui(rel) else None)

    def _changed(self, *_):
        if not self.file:
            return
        self.dirty = True
        self.file_title.set_label(f"{self.project} / {self.file} •")
        if self._is_gui(self.file):  # live preview while typing (debounced)
            if self._preview_timer:
                GLib.source_remove(self._preview_timer)
            self._preview_timer = GLib.timeout_add(300, self._update_preview)

    def _update_preview(self):
        self._preview_timer = 0
        start, end = self.buffer.get_bounds()
        self.preview.set_text(self.buffer.get_text(start, end, False))
        return False

    def _preview_clicked(self, it):
        self.toast(f'{it.cls} "{it.name}" clicked. Make it do something with '
                   f"a LocalScript (.MouseButton1Click).", "click")

    def _leave_file(self, then):
        """Never lose edits silently."""
        if not self.dirty:
            return then()
        dlg = Adw.MessageDialog(transient_for=self, heading="Save changes?",
                                body=f"{self.file} has unsaved changes.")
        dlg.add_response("discard", "Discard")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("save", "Save")
        dlg.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("save")
        dlg.set_close_response("cancel")

        def done(_d, r):
            if r == "save":
                self.save()
            if r in ("save", "discard"):
                self.dirty = False
                then()
        dlg.connect("response", done)
        dlg.present()

    # --- actions
    def need_project(self):
        if not self.project:
            self.toast("Create or pick a project first.")
            return False
        return True

    def new_project(self):
        def ok(name, _c):
            if self.guard(core.create_project, name):
                self._reload_projects(select=name.strip())
                self.toast(f'Project "{name.strip()}" created.', "success")
        ask_text(self, "New project", "A project holds one system, e.g. Inventory.",
                 "Project name", ok)

    def new_script(self):
        if not self.need_project():
            return
        kinds = ["Script (server)", "LocalScript (client)", "ModuleScript (shared)"]

        def ok(name, choice):
            kind, folder = {kinds[0]: ("Script", "server"),
                            kinds[1]: ("LocalScript", "client"),
                            kinds[2]: ("ModuleScript", "shared")}[choice]
            rel = self.guard(core.create_script, self.project, folder, name, kind)
            if rel:
                self._reload_files(select=rel)
                self.show_page("code")
                self.sounds.play("success")
        ask_text(self, "New script", None, "Script name", ok, ("Type", kinds))

    def new_gui(self):
        if not self.need_project():
            return

        def ok(name, _c):
            rel = self.guard(core.create_gui, self.project, name)
            if rel:
                self._reload_files(select=rel)
                self.show_page("preview")
                self.sounds.play("success")
        ask_text(self, "New GUI", "Creates a ScreenGui you can edit here, design "
                 "in the Figma tab, or change in Studio.", "GUI name", ok)

    def save(self):
        if not (self.project and self.file):
            return
        start, end = self.buffer.get_bounds()
        text = self.buffer.get_text(start, end, False)
        if self.file.endswith(".json"):
            try:
                json.loads(text)
            except json.JSONDecodeError as e:
                self.toast(f"Not saved: JSON error on line {e.lineno}.", "error")
                return
        if self.attempt(core.write_file, self.project, self.file, text):
            self.dirty = False
            self.file_title.set_label(f"{self.project} / {self.file}")
            if self.file.startswith("src/gui/"):
                core.write_project_file(self.project)

    def delete_file(self):
        if not (self.project and self.file):
            return
        rel = self.file

        def yes():
            if self.attempt(core.delete_file, self.project, rel):
                self.sounds.play("delete")
                if rel.startswith("src/gui/"):
                    figma.unlink(self.project, Path(rel).name.removesuffix(".model.json"))
                self.file, self.dirty = None, False
                self._set_editor(None, "")
                self._reload_files()
        confirm(self, "Delete file?", f"{rel} will be deleted permanently.", "Delete", yes)

    def delete_project(self):
        if not self.project:
            return
        name = self.project

        def yes():
            if self.rojo.project == name:
                self.sync_btn.set_active(False)
            if not self.attempt(core.delete_project, name):
                return
            self.sounds.play("delete")
            self.project = self.file = None
            self.dirty = False
            self._set_editor(None, "")
            self._reload_files()
            self._reload_projects()
        confirm(self, f'Delete "{name}"?', "Every script and GUI in it will be "
                "deleted permanently.", "Delete project", yes)

    def open_folder(self):
        if self.need_project():
            Gtk.FileLauncher.new(
                Gio.File.new_for_path(str(core.project_path(self.project)))
            ).launch(self, None, None)

    # --- Figma
    def figma_import(self, node_id=None):
        if not self.need_project():
            return
        if not figma.get_token():
            return self.figma.start_connect(then=lambda: self.figma_import(node_id))
        if not self.figma.uri:
            self.show_page("figma")
            return self.toast("Open a design file in the Figma tab, select a frame, "
                              "then press Import.")
        project, url = self.project, self.figma.uri
        scale = self.figma.sizing.get_selected() == 1
        self.toast("Importing from Figma…")

        def finished(result, err):
            if err:
                self.figma.update_account()  # a refused token is forgotten
            if isinstance(err, figma.NeedsFrameChoice):
                return self._pick_frame(err.frames)
            if isinstance(err, figma.NameTaken):
                return self._rename_import(project, err, scale)
            if err:
                return self.toast(err, "error")
            self._imported(project, *result)
        self.in_background(
            lambda: figma.import_from_tab(project, url, scale, node_id), finished)

    def _imported(self, project, name, rel, warns):
        for w in warns:
            self._log(f"Figma: {w}\n")
        if self.project == project:
            self._reload_files(select=rel)
            if self.file == rel:  # already open: show the new version
                self._open_file(rel)
            self.show_page("preview")
        self.toast(f'Imported "{name}".' + (" Check the log for notes." if warns else ""),
                   "import")

    def _rename_import(self, project, taken, scale):
        """Same name as another GUI: ask for a distinct name (no numbered copies)."""
        def ok(name, _c):
            try:
                result = figma.import_frame_as(project, name, taken.frame, taken.key,
                                               taken.node_id, scale)
            except figma.NameTaken as again:
                return self._rename_import(project, again, scale)
            except core.VaultError as e:
                self.toast(str(e), "error")
                return self._rename_import(project, taken, scale)
            self._imported(project, *result)
        ask_text(self, f'"{taken.name}" is taken',
                 "Another GUI already has that name. Give this frame its own "
                 "descriptive name, like ShopMenu or InventoryPanel.",
                 "GUI name", ok)

    def _pick_frame(self, frames):
        if not frames:
            return self.toast("This Figma file has no frames yet. Make one with F (Frame tool).",
                              "error")
        dlg = Adw.MessageDialog(transient_for=self, heading="Which frame?",
                                body="No frame was selected in Figma. Pick one to import:")
        lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        lb.add_css_class("boxed-list")
        label(lb, "Frames in this Figma file")
        for f in frames:
            lb.append(self._row(f"{f['name']}   ·   {f['page']}", f["id"]))
        lb.select_row(lb.get_row_at_index(0))
        dlg.set_extra_child(Gtk.ScrolledWindow(child=lb, min_content_height=220,
                                               hscrollbar_policy=Gtk.PolicyType.NEVER))
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("ok", "Import")
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("ok")
        dlg.set_close_response("cancel")

        def done(_d, r):
            row = lb.get_selected_row()
            if r == "ok" and row:
                self.figma_import(node_id=row.data)
        dlg.connect("response", done)
        dlg.present()

    def figma_refresh(self):
        if not self.need_project():
            return
        if not figma.linked_guis(self.project):
            return self.toast("No GUIs in this project came from Figma yet.")
        if not figma.get_token():
            return self.figma.start_connect(then=self.figma_refresh)
        project = self.project
        self.toast("Updating from Figma…")

        def finished(result, err):
            if err:
                self.figma.update_account()  # a refused token is forgotten
            if err:
                return self.toast(err, "error")
            names, problems = result
            for p in problems:
                self._log(f"Figma: {p}\n")
            if self.project == project and self.file and not self.dirty and \
                    self._is_gui(self.file):
                self._open_file(self.file)
            self.toast(f"Updated {len(names)} GUI(s) from Figma." +
                       (" Studio is updating too." if self.rojo.running else ""),
                       "import" if names else "error")
        self.in_background(lambda: figma.refresh_all(project), finished)

    def figma_signout(self):
        confirm(self, "Sign out of Figma?",
                "Removes the app's Figma connection and the Figma tab's sign-in "
                "and cookies. Your imported GUIs stay.", "Sign out", self.figma.sign_out)

    # --- sync / build
    def _toggle_sync(self, btn):
        if btn.get_active():
            if not self.need_project():
                btn.set_active(False)
                return
            self.save()
            port = self.app.settings.port
            if self.attempt(self.rojo.start, self.project, port):
                self._log(f"--- Syncing {self.project} on localhost:{port}. "
                          "In Studio: Plugins → Rojo → Connect.\n")
                self.sounds.play("sync_on")
            else:
                btn.set_active(False)
        elif self.rojo.running:
            self.rojo.stop()
            self.sounds.play("sync_off")

    def _rojo_exited(self, code):
        self._log(f"--- Rojo stopped (exit code {code}).\n")
        self.sync_btn.set_active(False)

    def _log(self, line):
        buf = self.log_view.get_buffer()
        buf.insert(buf.get_end_iter(), line)
        if buf.get_line_count() > 500:
            buf.delete(buf.get_start_iter(), buf.get_iter_at_line(100)[1])
        self.log_view.scroll_to_iter(buf.get_end_iter(), 0, False, 0, 0)

    def build(self):
        if not self.need_project():
            return
        self.save()
        dialog = Gtk.FileDialog(title="Save place file", initial_name=f"{self.project}.rbxl")

        def done(d, res):
            try:
                f = d.save_finish(res)
            except GLib.Error:
                return
            out = self.guard(core.rojo_build, self.project, f.get_path())
            if out:
                self.toast(f"Built {Path(out).name}. Open it in Studio.", "success")
        dialog.save(self, None, done)

    def help_sync(self):
        rojo = core.find_rojo()
        dlg = Adw.MessageDialog(transient_for=self, heading="Setting up sync", body=(
            f"Rojo: {'built in (' + rojo + ')' if rojo else 'NOT found'}\n\n"
            "1. Run Roblox Studio (on Linux, through Vinegar from the COSMIC Store).\n"
            "2. In Studio, get the Rojo plugin from the Creator Store.\n"
            "3. Make sure the plugin's version matches the Rojo shown above.\n"
            "4. Click the sync button here, then in Studio press "
            "Plugins → Rojo → Connect.\n\n"
            "Saves here, and GUIs updated from Figma, then appear in Studio."))
        dlg.add_response("ok", "OK")
        dlg.present()

    def shortcuts(self):
        lines = ("Alt+1 / 2 / 3  Code / Preview / Figma tabs\n"
                 "Ctrl+Shift+N  New project\nCtrl+N  New script\nCtrl+G  New GUI\n"
                 "Ctrl+S  Save\nCtrl+I  Import selected Figma frame\n"
                 "Ctrl+Shift+R  Update GUIs from Figma\nCtrl+R  Start/stop sync\n"
                 "Ctrl+B  Build place file\nF10  Main menu\n"
                 "Tab / Shift+Tab  Move between areas\nArrow keys  Move in lists\n"
                 "Ctrl+?  This list")
        dlg = Adw.MessageDialog(transient_for=self, heading="Keyboard shortcuts", body=lines)
        dlg.add_response("ok", "OK")
        dlg.present()

    def uninstall(self):
        def yes():
            self.rojo.stop()
            self.sounds.play("delete")
            removing = self.attempt(core.uninstall_app) and core.can_reach_host()
            if removing:
                GLib.timeout_add(400, lambda: self.app.quit() or False)
                return
            # Sandbox can't remove itself: data is gone, finish in the store.
            dlg = Adw.MessageDialog(
                transient_for=self, heading="Your data is deleted",
                body="One last step: in the COSMIC Store open Installed, find "
                     "Roblox Vault and press Uninstall.")
            dlg.add_response("ok", "Close Roblox Vault")
            dlg.connect("response", lambda *_: self.app.quit())
            dlg.present()
        confirm(self, "Uninstall Roblox Vault?",
                "This removes the app and its icon, and permanently deletes every "
                "project, script, GUI, note, setting, your Figma connection and "
                "the Figma tab's cookies, including anything left by the older zip "
                "version. Export anything you want to keep first (Menu → Open "
                "project folder). This can't be undone.",
                "Uninstall and delete everything", yes)

    def delete_all(self):
        def yes():
            self.rojo.stop()
            if self.attempt(core.delete_all_data):
                self.app.quit()
        confirm(self, "Delete all my data?",
                "This permanently deletes every project, script, GUI, note, "
                "setting, your Figma connection and the Figma tab's cookies from "
                "this computer, then closes the app. It can't be undone.",
                "Delete everything", yes)

    def about(self):
        b = business()
        about = Adw.AboutWindow(
            transient_for=self, application_name=core.APP_NAME,
            application_icon=core.APP_ID, version=core.APP_VERSION,
            developer_name=b.get("owner_name") or "Unknown",
            license_type=Gtk.License.MIT_X11, website=b.get("website") or "",
            issue_url=b.get("contact") or "",
            comments="Store, design, preview and sync your Roblox systems.\n"
                     "Not affiliated with or endorsed by Roblox Corporation or Figma, Inc.")
        about.add_legal_section("Rojo", "Copyright the Rojo developers",
                                Gtk.License.MPL_2_0, None)
        about.add_legal_section("WebKitGTK", "Copyright the WebKit contributors",
                                Gtk.License.LGPL_2_1, None)
        about.add_legal_section("Icon and sound effects",
                                "Original work made for Roblox Vault",
                                Gtk.License.MIT_X11, None)
        about.present()

    def _on_close(self, *_):
        if self.dirty:
            self._leave_file(self.close)
            return True
        self.figma.stop_connect()
        self.rojo.stop()
        return False


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=core.APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.settings = None
        self.win = None

    def do_activate(self):
        if self.win:
            return self.win.present()
        self.settings = core.Settings()
        if self.settings.has_consent:
            self._main()
        else:
            ConsentWindow(self, self._consented).present()

    def _consented(self, terms, privacy, age):
        self.settings.record_consent(terms, privacy, age)
        self._main()

    def _main(self):
        self.win = MainWindow(self)
        self.win.present()
        try:
            moved = core.migrate_legacy_projects()
        except OSError:
            moved = 0
        if moved:
            self.win._reload_projects()
            self.win.toast(f"Brought over {moved} project(s) from the older version.",
                           "success")

    def do_startup(self):
        Adw.Application.do_startup(self)
        # Running from source: find the icon next to the code.
        icons = Path(__file__).resolve().parent.parent / "data" / "icons"
        display = Gdk.Display.get_default()
        if icons.is_dir() and display:
            Gtk.IconTheme.get_for_display(display).add_search_path(str(icons))
        Gtk.Window.set_default_icon_name(core.APP_ID)


def main():
    return App().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())

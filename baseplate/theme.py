"""Baseplate's dark studio look.

One accent colour (baseplate mint) on graphite. Text colours are chosen for
at least 4.5:1 contrast on every surface they sit on (checked in
tests/test_theme.py). When the system's high-contrast mode is on, the custom
colours step aside so the system theme can do its job.
"""
from __future__ import annotations

PALETTE = {
    "bg": "#111316",        # window
    "sidebar": "#16191d",
    "panel": "#1b1f24",     # headerbar, assistant, cards
    "raised": "#232931",    # hover, inputs
    "code": "#0c0e11",
    "border": "#2b323b",
    "text": "#e8ebef",
    "dim": "#a3acb6",
    "accent": "#3ddc97",
    "accent_hover": "#62e6ad",
    "on_accent": "#05200f",
    "error": "#ff7b72",
    "warning": "#f2cc60",
}

CSS = """
@define-color accent_bg_color {accent};
@define-color accent_fg_color {on_accent};
@define-color accent_color {accent_hover};
@define-color window_bg_color {bg};
@define-color window_fg_color {text};
@define-color view_bg_color {bg};
@define-color view_fg_color {text};
@define-color headerbar_bg_color {panel};
@define-color headerbar_fg_color {text};
@define-color headerbar_backdrop_color {panel};
@define-color sidebar_bg_color {sidebar};
@define-color sidebar_fg_color {text};
@define-color secondary_sidebar_bg_color {panel};
@define-color card_bg_color {panel};
@define-color popover_bg_color {panel};
@define-color dialog_bg_color {panel};
@define-color destructive_color {error};
@define-color error_color {error};
@define-color warning_color {warning};

:root {{
  --accent-bg-color: {accent};
  --accent-fg-color: {on_accent};
  --accent-color: {accent_hover};
  --window-bg-color: {bg};
  --window-fg-color: {text};
  --view-bg-color: {bg};
  --view-fg-color: {text};
  --headerbar-bg-color: {panel};
  --headerbar-fg-color: {text};
  --sidebar-bg-color: {sidebar};
  --sidebar-fg-color: {text};
  --secondary-sidebar-bg-color: {panel};
  --card-bg-color: {panel};
  --popover-bg-color: {panel};
  --dialog-bg-color: {panel};
  --destructive-color: {error};
  --error-color: {error};
  --warning-color: {warning};
}}

headerbar {{ border-bottom: 1px solid {border}; box-shadow: none; }}
.dim-label, .bp-dim {{ color: {dim}; opacity: 1; }}

.bp-brand {{ font-weight: 800; font-size: 17px; letter-spacing: 0.02em; }}
.bp-brand-dot {{ color: {accent}; }}
.bp-section {{
  font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
  color: {dim}; margin: 14px 12px 4px 12px;
}}
.bp-sidebar {{ background: {sidebar}; border-right: 1px solid {border}; }}
.bp-sidebar list {{ background: transparent; }}
.bp-sidebar row {{ border-radius: 8px; margin: 1px 6px; padding: 2px 4px; }}
.bp-sidebar row:selected {{ background: alpha({accent}, 0.16); color: {text}; }}
.bp-sidebar row:selected .bp-row-icon {{ color: {accent}; }}
.bp-group-header {{ font-size: 11px; font-weight: 700; color: {dim}; margin: 10px 14px 2px 14px; }}

.bp-pathbar {{ background: {panel}; border-bottom: 1px solid {border}; padding: 6px 10px; }}
.bp-path {{ font-family: monospace; color: {dim}; }}
.bp-path-name {{ font-family: monospace; color: {text}; font-weight: 600; }}

.bp-statusbar {{
  background: {sidebar}; border-top: 1px solid {border};
  padding: 3px 10px; font-size: 12px;
}}
.bp-chip {{
  border-radius: 999px; padding: 1px 10px; background: {raised};
  color: {text}; font-size: 12px;
}}
.bp-chip.on {{ background: alpha({accent}, 0.18); color: {accent_hover}; }}
.bp-chip.off {{ color: {dim}; }}

.bp-assistant {{ background: {panel}; border-left: 1px solid {border}; }}
.bp-bubble {{ border-radius: 12px; padding: 10px 12px; }}
.bp-bubble.user {{ background: alpha({accent}, 0.14); }}
.bp-bubble.ai {{ background: {raised}; }}
.bp-bubble.err {{ background: alpha({error}, 0.14); }}
.bp-who {{ font-size: 11px; font-weight: 700; color: {dim}; }}
.bp-code {{
  background: {code}; border: 1px solid {border}; border-radius: 8px;
  font-family: monospace; font-size: 12.5px; padding: 8px 10px;
}}
.bp-codebar button {{ min-height: 24px; padding: 0 8px; font-size: 12px; }}
.bp-input {{ background: {raised}; border-radius: 10px; padding: 6px 8px; }}
.bp-input textview, .bp-input text {{ background: transparent; }}
.bp-suggestion {{ border-radius: 999px; padding: 4px 12px; }}

.bp-log {{ background: {code}; font-family: monospace; font-size: 12px; }}
"""


def css_text() -> str:
    return CSS.format(**PALETTE)


def _lum(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def apply(display=None):
    """Turn on the dark studio look, unless the system wants high contrast."""
    from gi.repository import Adw, Gdk, Gtk
    style = Adw.StyleManager.get_default()
    style.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
    if style.get_high_contrast():
        return
    provider = Gtk.CssProvider()
    provider.load_from_string(css_text())
    Gtk.StyleContext.add_provider_for_display(
        display or Gdk.Display.get_default(), provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

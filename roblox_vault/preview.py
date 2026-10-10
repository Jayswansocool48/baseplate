"""Render a Rojo .model.json ScreenGui roughly the way Roblox would.

layout() is plain Python (testable without GTK). draw() paints the result with
cairo + Pango. It's an approximation: Roblox fonts, images, layouts
(UIListLayout etc.) and scripts aren't simulated.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEVICES = [("Desktop 1920×1080", 1920, 1080), ("Laptop 1366×768", 1366, 768),
           ("Tablet 1024×768", 1024, 768), ("Phone 844×390", 844, 390)]
TOPBAR_INSET = 58  # Roblox's top bar height; GUIs start below it unless IgnoreGuiInset

GUI_OBJECTS = {"Frame", "TextLabel", "TextButton", "TextBox", "ImageLabel",
               "ImageButton", "ScrollingFrame", "CanvasGroup", "ViewportFrame"}
TEXT_CLASSES = {"TextLabel", "TextButton", "TextBox"}
DEFAULT_TEXT = {"TextLabel": "Label", "TextButton": "Button", "TextBox": ""}
DEFAULT_BG = (0.639, 0.635, 0.647)
DEFAULT_TEXT_COLOR = (27 / 255, 42 / 255, 53 / 255)
TYPED = {"UDim2", "UDim", "Color3", "Vector2", "Float32", "Float64", "Int32",
         "Int64", "Bool", "String", "Enum", "Content"}


def prop(props: dict, key: str, default=None):
    """Read a property in Rojo's explicit ({"Float32": 1}) or implicit (1) form."""
    v = props.get(key, default)
    if isinstance(v, dict) and len(v) == 1:
        (k, inner), = v.items()
        if k in TYPED:
            return inner
    return v


def _udim2(v, default):
    try:
        (xs, xo), (ys, yo) = v
        return float(xs), float(xo), float(ys), float(yo)
    except (TypeError, ValueError):
        return default


def _color(v, default):
    try:
        r, g, b = v
        return float(r), float(g), float(b)
    except (TypeError, ValueError):
        return default


@dataclass
class Item:
    name: str
    cls: str
    x: float
    y: float
    w: float
    h: float
    path: str
    clip: tuple | None = None          # (x, y, w, h) to clip to
    bg: tuple | None = None            # (r, g, b, alpha)
    radius: float = 0
    stroke: tuple | None = None        # (r, g, b, alpha, thickness)
    text: str | None = None
    text_color: tuple = DEFAULT_TEXT_COLOR + (1,)
    text_size: float = 14
    text_x: int = 2                    # 0 left, 1 right, 2 center
    text_y: int = 1                    # 0 top, 1 center, 2 bottom
    wrapped: bool = False
    scaled: bool = False
    image: bool = False
    depth: int = 0
    notes: list = field(default_factory=list)

    def contains(self, px, py):
        if self.clip:
            cx, cy, cw, ch = self.clip
            if not (cx <= px <= cx + cw and cy <= py <= cy + ch):
                return False
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h

    @property
    def clickable(self):
        return self.cls in ("TextButton", "ImageButton")


def _children(node):
    return node.get("Children") or []


def _modifier(node, cls):
    for c in _children(node):
        if c.get("ClassName") == cls:
            return c.get("Properties") or {}
    return None


def _intersect(a, b):
    if a is None:
        return b
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2 = min(a[0] + a[2], b[0] + b[2])
    y2 = min(a[1] + a[3], b[1] + b[3])
    return (x1, y1, max(0, x2 - x1), max(0, y2 - y1))


def layout(model: dict, sw: int, sh: int) -> tuple[list[Item], list[str]]:
    """ScreenGui model -> Items in paint order (back to front), plus notes."""
    notes: list[str] = []
    if not isinstance(model, dict) or model.get("ClassName") != "ScreenGui":
        return [], ["This file isn't a ScreenGui, so there's nothing to preview."]
    sp = model.get("Properties") or {}
    if prop(sp, "Enabled", True) is False:
        notes.append("This ScreenGui has Enabled = false, so Roblox won't show it.")
    top = 0 if prop(sp, "IgnoreGuiInset", False) else TOPBAR_INSET
    items: list[Item] = []
    warned = set()

    def walk(nodes, px, py, pw, ph, clip, path, depth):
        kids = [n for n in nodes if n.get("ClassName") in GUI_OBJECTS]
        for n in _children_of_unknown(nodes):
            cls = n.get("ClassName")
            if cls in ("UIListLayout", "UIGridLayout", "UIAspectRatioConstraint",
                       "UIScale") and cls not in warned:
                warned.add(cls)
                notes.append(f"{cls} isn't simulated; positions may differ in Roblox.")
        # stable sort by ZIndex, like ZIndexBehavior.Sibling
        kids = sorted(enumerate(kids),
                      key=lambda t: (int(prop(t[1].get("Properties") or {}, "ZIndex", 1) or 1), t[0]))
        for _i, n in kids:
            p = n.get("Properties") or {}
            if prop(p, "Visible", True) is False:
                continue
            cls = n["ClassName"]
            name = n.get("Name", cls)
            sxs, sxo, sys_, syo = _udim2(prop(p, "Size"), (0, 100, 0, 100))
            pxs, pxo, pys, pyo = _udim2(prop(p, "Position"), (0, 0, 0, 0))
            ax, ay = prop(p, "AnchorPoint", [0, 0]) or [0, 0]
            w, h = sxs * pw + sxo, sys_ * ph + syo
            x = px + pxs * pw + pxo - float(ax) * w
            y = py + pys * ph + pyo - float(ay) * h
            it = Item(name=name, cls=cls, x=x, y=y, w=w, h=h,
                      path=f"{path}/{name}", clip=clip, depth=depth)
            alpha = 1 - float(prop(p, "BackgroundTransparency", 0) or 0)
            if alpha > 0:
                it.bg = _color(prop(p, "BackgroundColor3"), DEFAULT_BG) + (alpha,)
            corner = _modifier(n, "UICorner")
            if corner is not None:
                cs, co = prop(corner, "CornerRadius", [0, 8]) or [0, 8]
                it.radius = min(float(cs) * min(w, h) + float(co), min(w, h) / 2)
            stroke = _modifier(n, "UIStroke")
            if stroke is not None:
                sa = 1 - float(prop(stroke, "Transparency", 0) or 0)
                it.stroke = _color(prop(stroke, "Color"), (0, 0, 0)) + (
                    sa, float(prop(stroke, "Thickness", 1) or 1))
            if cls in TEXT_CLASSES:
                it.text = str(prop(p, "Text", DEFAULT_TEXT[cls]) or "")
                ta = 1 - float(prop(p, "TextTransparency", 0) or 0)
                it.text_color = _color(prop(p, "TextColor3"), DEFAULT_TEXT_COLOR) + (ta,)
                it.text_size = float(prop(p, "TextSize", 14) or 14)
                it.text_x = int(prop(p, "TextXAlignment", 2))
                it.text_y = int(prop(p, "TextYAlignment", 1))
                it.wrapped = bool(prop(p, "TextWrapped", False))
                it.scaled = bool(prop(p, "TextScaled", False))
            if cls in ("ImageLabel", "ImageButton"):
                it.image = True
            items.append(it)
            child_clip = _intersect(clip, (x, y, w, h)) if prop(p, "ClipsDescendants", False) else clip
            pad = _modifier(n, "UIPadding")
            cx, cy, cw, ch = x, y, w, h
            if pad is not None:
                l = _pad(pad, "PaddingLeft", w)
                r = _pad(pad, "PaddingRight", w)
                t = _pad(pad, "PaddingTop", h)
                b = _pad(pad, "PaddingBottom", h)
                cx, cy, cw, ch = x + l, y + t, max(0, w - l - r), max(0, h - t - b)
            walk(_children(n), cx, cy, cw, ch, child_clip, it.path, depth + 1)

    walk(_children(model), 0, top, sw, sh - top, None, "", 0)
    return items, notes


def _children_of_unknown(nodes):
    return [n for n in nodes if n.get("ClassName") not in GUI_OBJECTS]


def _pad(p, key, size):
    v = prop(p, key, [0, 0]) or [0, 0]
    try:
        return float(v[0]) * size + float(v[1])
    except (TypeError, ValueError, IndexError):
        return 0


def hit(items: list[Item], px: float, py: float) -> Item | None:
    """Topmost item under a point (items are back-to-front)."""
    for it in reversed(items):
        if it.contains(px, py):
            return it
    return None


# ---------------------------------------------------------------- drawing

def _rounded(cr, x, y, w, h, r):
    import math
    if r <= 0:
        cr.rectangle(x, y, w, h)
        return
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def draw(cr, items, sw, sh, top_inset_shown, hover=None, pressed=None, font="Sans"):
    """Paint items onto a cairo context already scaled to screen pixels."""
    from gi.repository import Pango, PangoCairo

    # "game world" backdrop, so transparent GUIs are visible
    cr.set_source_rgb(0.36, 0.55, 0.42)
    cr.rectangle(0, 0, sw, sh)
    cr.fill()
    cr.set_source_rgb(0.47, 0.70, 0.88)
    cr.rectangle(0, 0, sw, sh * 0.55)
    cr.fill()
    if top_inset_shown:
        cr.set_source_rgba(0, 0, 0, 0.25)
        cr.rectangle(0, 0, sw, TOPBAR_INSET)
        cr.fill()

    for it in items:
        cr.save()
        if it.clip:
            cr.rectangle(*it.clip)
            cr.clip()
        if it.bg:
            r, g, b, a = it.bg
            if it is pressed:
                r, g, b = r * 0.7, g * 0.7, b * 0.7
            elif it is hover and it.clickable:
                r, g, b = r * 0.85, g * 0.85, b * 0.85
            cr.set_source_rgba(r, g, b, a)
            _rounded(cr, it.x, it.y, it.w, it.h, it.radius)
            cr.fill()
        if it.image:  # placeholder: Roblox images can't be fetched here
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.35)
            _rounded(cr, it.x, it.y, it.w, it.h, it.radius)
            cr.fill()
            cr.set_source_rgba(1, 1, 1, 0.7)
            cr.set_line_width(2)
            cr.move_to(it.x, it.y)
            cr.line_to(it.x + it.w, it.y + it.h)
            cr.move_to(it.x + it.w, it.y)
            cr.line_to(it.x, it.y + it.h)
            cr.stroke()
        if it.stroke and it.stroke[4] > 0:
            r, g, b, a, t = it.stroke
            cr.set_source_rgba(r, g, b, a)
            cr.set_line_width(t)
            _rounded(cr, it.x - t / 2, it.y - t / 2, it.w + t, it.h + t, it.radius + t / 2)
            cr.stroke()
        if it.text:
            layout_ = PangoCairo.create_layout(cr)
            size = it.text_size
            desc = Pango.FontDescription.from_string(font)
            desc.set_absolute_size(size * Pango.SCALE)
            layout_.set_font_description(desc)
            layout_.set_text(it.text, -1)
            if it.wrapped or it.scaled:
                layout_.set_width(int(max(1, it.w) * Pango.SCALE))
                layout_.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout_.set_alignment({0: Pango.Alignment.LEFT, 1: Pango.Alignment.RIGHT}
                                  .get(it.text_x, Pango.Alignment.CENTER))
            _tw, th = layout_.get_pixel_size()
            if it.scaled and th > 0:  # shrink/grow to fit, like TextScaled
                while th > it.h and size > 4:
                    size *= 0.9
                    desc.set_absolute_size(size * Pango.SCALE)
                    layout_.set_font_description(desc)
                    _tw, th = layout_.get_pixel_size()
            tw, th = layout_.get_pixel_size()
            if not (it.wrapped or it.scaled):
                tx = {0: it.x, 1: it.x + it.w - tw}.get(it.text_x, it.x + (it.w - tw) / 2)
            else:
                tx = it.x
            ty = {0: it.y, 2: it.y + it.h - th}.get(it.text_y, it.y + (it.h - th) / 2)
            cr.rectangle(it.x, it.y, it.w, it.h)  # text is clipped to its box
            cr.clip()
            cr.set_source_rgba(*it.text_color)
            cr.move_to(tx, ty)
            PangoCairo.show_layout(cr, layout_)
        cr.restore()

    if hover:  # outline what the mouse is over (helps find layers)
        cr.set_source_rgba(1, 0.8, 0.1, 0.95)
        cr.set_line_width(2)
        cr.rectangle(hover.x, hover.y, hover.w, hover.h)
        cr.stroke()

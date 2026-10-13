import unittest

from baseplate import theme

P = theme.PALETTE


class ThemeTests(unittest.TestCase):
    def test_text_contrast_meets_wcag_aa(self):
        for surface in ("bg", "sidebar", "panel", "raised", "code"):
            for fg in ("text", "dim"):
                self.assertGreaterEqual(theme.contrast(P[fg], P[surface]), 4.5,
                                        f"{fg} on {surface}")
        self.assertGreaterEqual(theme.contrast(P["on_accent"], P["accent"]), 4.5)
        for fg in ("accent", "accent_hover", "error", "warning"):
            self.assertGreaterEqual(theme.contrast(P[fg], P["panel"]), 4.5, fg)

    def test_css_renders(self):
        css = theme.css_text()
        self.assertIn("--accent-bg-color: #3ddc97", css)
        self.assertNotIn("{", css.split(":root")[0].split("@define-color")[0])


if __name__ == "__main__":
    unittest.main()

import json
import unittest

from baseplate import core, figma, preview
from tests.test_figma import FRAME


class PreviewTests(unittest.TestCase):
    def test_template_gui_lays_out_centered(self):
        items, notes = preview.layout(core.gui_template("Shop"), 1920, 1080)
        main = items[0]
        self.assertEqual((main.w, main.h), (320, 180))
        top = preview.TOPBAR_INSET
        self.assertAlmostEqual(main.x, 1920 / 2 - 160)
        self.assertAlmostEqual(main.y, top + (1080 - top) / 2 - 90)
        self.assertEqual(main.radius, 8)  # UICorner default
        title = items[1]
        self.assertEqual(title.text, "Shop")
        self.assertIsNone(title.bg)  # BackgroundTransparency 1

    def test_figma_import_previews_and_scales(self):
        model, _ = figma.to_screengui(FRAME, scale=True)
        model = json.loads(json.dumps(model))  # same as reading the saved file
        big, _ = preview.layout(model, 1920, 1080)
        small, _ = preview.layout(model, 844, 390)
        title_big = next(i for i in big if i.name == "Title")
        title_small = next(i for i in small if i.name == "Title")
        self.assertAlmostEqual(title_big.w, 960)
        self.assertAlmostEqual(title_small.w, 422)
        names = [i.name for i in big]
        self.assertNotIn("Hidden", names)  # Visible = false is skipped
        btn = next(i for i in big if i.name == "CloseButton")
        self.assertTrue(btn.clickable)
        self.assertEqual(btn.stroke[4], 2)
        self.assertIs(preview.hit(big, btn.x + 1, btn.y + 1), btn)

    def test_zindex_paint_order_and_clipping(self):
        model = {"ClassName": "ScreenGui", "Properties": {"IgnoreGuiInset": True},
                 "Children": [{"Name": "Box", "ClassName": "Frame", "Properties": {
                     "Size": [[0, 100], [0, 100]], "ClipsDescendants": True},
                     "Children": [
                         {"Name": "Top", "ClassName": "Frame", "Properties": {"ZIndex": 5}},
                         {"Name": "Bottom", "ClassName": "Frame", "Properties": {"ZIndex": 1}},
                         {"Name": "Pad", "ClassName": "UIPadding", "Properties": {
                             "PaddingLeft": {"UDim": [0, 10]}}},
                         {"Name": "List", "ClassName": "UIListLayout"}]}]}
        items, notes = preview.layout(model, 800, 600)
        self.assertEqual([i.name for i in items], ["Box", "Bottom", "Top"])
        self.assertEqual(items[1].x, 10)  # UIPadding
        self.assertEqual(items[2].clip, (0, 0, 100, 100))
        self.assertTrue(any("UIListLayout" in n for n in notes))

    def test_not_a_gui(self):
        items, notes = preview.layout({"ClassName": "Folder"}, 800, 600)
        self.assertEqual(items, [])
        self.assertTrue(notes)


if __name__ == "__main__":
    unittest.main()

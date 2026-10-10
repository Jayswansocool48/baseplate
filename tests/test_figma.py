import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from roblox_vault import core, figma

# Shaped like GET /v1/files/:key/nodes -> nodes[id].document
FRAME = {
    "id": "1:2", "name": "Inventory", "type": "FRAME", "clipsContent": True,
    "absoluteBoundingBox": {"x": 100, "y": 50, "width": 400, "height": 300},
    "fills": [{"type": "SOLID", "color": {"r": 0.1, "g": 0.1, "b": 0.12, "a": 1}}],
    "cornerRadius": 12,
    "children": [
        {"id": "1:3", "name": "Title", "type": "TEXT", "characters": "Inventory",
         "absoluteBoundingBox": {"x": 120, "y": 60, "width": 200, "height": 30},
         "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1, "a": 1}}],
         "style": {"fontSize": 24, "textAlignHorizontal": "CENTER",
                   "textAlignVertical": "CENTER"}},
        {"id": "1:4", "name": "CloseButton", "type": "RECTANGLE",
         "absoluteBoundingBox": {"x": 460, "y": 60, "width": 30, "height": 30},
         "fills": [{"type": "SOLID", "color": {"r": 0.9, "g": 0.2, "b": 0.2, "a": 1},
                    "opacity": 0.5}],
         "strokes": [{"type": "SOLID", "color": {"r": 0, "g": 0, "b": 0, "a": 1}}],
         "strokeWeight": 2},
        {"id": "1:5", "name": "Icon", "type": "RECTANGLE",
         "absoluteBoundingBox": {"x": 120, "y": 100, "width": 64, "height": 64},
         "fills": [{"type": "IMAGE", "imageRef": "abc"}]},
        {"id": "1:6", "name": "Hidden", "type": "FRAME", "visible": False,
         "absoluteBoundingBox": {"x": 100, "y": 50, "width": 10, "height": 10}},
    ],
}


class FigmaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_DATA_HOME"] = str(Path(self.tmp.name) / "data")
        os.environ["XDG_CONFIG_HOME"] = str(Path(self.tmp.name) / "config")

    def tearDown(self):
        self.tmp.cleanup()

    def test_layer_names_lose_version_tags(self):
        self.assertEqual(figma.clean_name("Shop Frame V3"), "Shop Frame")
        self.assertEqual(figma.clean_name("CloseButton_final"), "CloseButton")
        self.assertEqual(figma.clean_name("🔥"), "Element")

    def test_parse_url(self):
        self.assertEqual(figma.parse_url(
            "https://www.figma.com/design/AbC123/My-UI?node-id=12-34&t=x"), ("AbC123", "12:34"))
        self.assertEqual(figma.parse_url(
            "https://www.figma.com/design/Main/branch/Br4nch/UI?node-id=1-2"), ("Br4nch", "1:2"))
        self.assertEqual(figma.parse_url("https://www.figma.com/design/K/UI"), ("K", None))
        self.assertEqual(figma.parse_url("https://www.figma.com/files/recents"), (None, None))
        self.assertEqual(figma.parse_url("https://evil.com/design/K/x"), (None, None))

    def test_find_token_in_clipboard_text(self):
        tok = "figd_" + "a1B2-c3_" * 5
        self.assertEqual(figma.find_token(f"  {tok}\n"), tok)
        self.assertIsNone(figma.find_token("my password is hunter2"))
        self.assertIsNone(figma.find_token(None))

    def test_convert_offset(self):
        model, warns = figma.to_screengui(FRAME, scale=False)
        self.assertEqual(model["ClassName"], "ScreenGui")
        root = model["Children"][0]
        self.assertEqual(root["ClassName"], "Frame")
        self.assertEqual(root["Properties"]["Size"], {"UDim2": [[0, 400], [0, 300]]})
        kids = {c["Name"]: c for c in root["Children"]}
        self.assertEqual(kids["Corner"]["Properties"]["CornerRadius"], {"UDim": [0, 12]})
        title = kids["Title"]
        self.assertEqual(title["ClassName"], "TextLabel")
        self.assertEqual(title["Properties"]["Position"], {"UDim2": [[0, 20], [0, 10]]})
        self.assertEqual(title["Properties"]["TextXAlignment"], {"Enum": 2})
        btn = kids["CloseButton"]
        self.assertEqual(btn["ClassName"], "TextButton")
        self.assertEqual(btn["Properties"]["BackgroundTransparency"], {"Float32": 0.5})
        self.assertEqual(btn["Children"][0]["ClassName"], "UIStroke")
        self.assertEqual(kids["Icon"]["ClassName"], "ImageLabel")
        self.assertEqual(kids["Hidden"]["Properties"]["Visible"], {"Bool": False})
        self.assertTrue(any("image" in w for w in warns))

    def test_convert_scale(self):
        model, _ = figma.to_screengui(FRAME, scale=True)
        root = model["Children"][0]
        self.assertEqual(root["Properties"]["Size"], {"UDim2": [[1, 0], [1, 0]]})
        title = next(c for c in root["Children"] if c["Name"] == "Title")
        self.assertEqual(title["Properties"]["Size"], {"UDim2": [[0.5, 0], [0.1, 0]]})

    def test_import_from_tab_and_refresh(self):
        core.create_project("Inv")
        calls = []

        def fake_fetch(key, ids):
            calls.append((key, list(ids)))
            return {i: FRAME for i in ids}
        tab = "https://www.figma.com/design/KEY/UI?node-id=1-2"
        name, rel, _ = figma.import_from_tab("Inv", tab, False, _fetch=fake_fetch)
        self.assertEqual(name, "Inventory")  # named after the Figma frame
        self.assertEqual(rel, "src/gui/Inventory.model.json")
        json.loads(core.read_file("Inv", rel))
        proj = json.loads((core.project_path("Inv") / "default.project.json").read_text())
        self.assertIn("Inventory", proj["tree"]["StarterGui"])
        self.assertNotIn("figma-links.json", " ".join(core.list_files("Inv")))
        # same frame again -> same GUI, not a copy
        name2, _, _ = figma.import_from_tab("Inv", tab, False, _fetch=fake_fetch)
        self.assertEqual(name2, "Inventory")
        # a different frame with the same name -> ask for a name, no "Inventory2"
        other = "https://www.figma.com/design/KEY/UI?node-id=9-9"
        with self.assertRaises(figma.NameTaken) as cm:
            figma.import_from_tab("Inv", other, False, _fetch=fake_fetch)
        taken = cm.exception
        before = len(calls)
        with self.assertRaises(core.VaultError):  # version tags are refused
            figma.import_frame_as("Inv", "InventoryV2", taken.frame, taken.key,
                                  taken.node_id, False)
        name3, _, _ = figma.import_frame_as("Inv", "InventoryShop", taken.frame,
                                            taken.key, taken.node_id, False)
        self.assertEqual(name3, "InventoryShop")
        self.assertEqual(len(calls), before, "renaming must not cost a Figma request")
        calls.clear()
        names, problems = figma.refresh_all("Inv", _fetch=fake_fetch)
        self.assertEqual(sorted(names), ["Inventory", "InventoryShop"])
        self.assertEqual(len(calls), 1, "one request per Figma file")
        self.assertEqual(sorted(calls[0][1]), ["1:2", "9:9"])

    def test_no_frame_selected_offers_picker(self):
        core.create_project("Inv")
        frames = [{"id": "1:2", "name": "Inventory", "page": "Page 1"}]
        with self.assertRaises(figma.NeedsFrameChoice) as cm:
            figma.import_from_tab("Inv", "https://www.figma.com/design/KEY/UI", False,
                                  _fetch=lambda k, i: {}, _frames=lambda k: frames)
        self.assertEqual(cm.exception.frames, frames)
        with self.assertRaises(core.VaultError):
            figma.import_from_tab("Inv", "https://www.figma.com/files/recents", False)

    def test_token_private_and_deleted(self):
        self.assertIsNone(figma.get_token())
        tok = "figd_" + "x" * 30
        figma.set_token(tok)
        self.assertEqual(figma.get_token(), tok)
        with self.assertRaises(core.VaultError):
            figma.set_token("not a token")
        self.assertEqual(stat.S_IMODE(figma.token_path().stat().st_mode), 0o600)
        core.delete_all_data()
        self.assertIsNone(figma.get_token())

    def test_refused_token_is_explained_and_forgotten(self):
        import io
        import urllib.error
        from unittest import mock
        figma.set_token("figd_" + "x" * 30)

        def refuse(body):
            def fake(*_a, **_k):
                raise urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(body))
            return fake
        with mock.patch("urllib.request.urlopen", refuse(b'{"status":403,"err":"Invalid token"}')):
            with self.assertRaises(core.VaultError) as cm:
                figma.fetch_nodes("KEY", ["1:2"])
        self.assertIn("Invalid token", str(cm.exception))
        self.assertIsNone(figma.get_token(), "a rejected token must be deleted")
        # a permission problem on one file keeps the token
        figma.set_token("figd_" + "x" * 30)
        with mock.patch("urllib.request.urlopen", refuse(b'{"err":"Forbidden"}')):
            with self.assertRaises(core.VaultError) as cm:
                figma.fetch_nodes("KEY", ["1:2"])
        self.assertIn("File content", str(cm.exception))
        self.assertIsNotNone(figma.get_token())

    def test_no_token_means_no_network(self):
        with self.assertRaises(core.VaultError):
            figma.fetch_nodes("KEY", ["1:2"])


if __name__ == "__main__":
    unittest.main()

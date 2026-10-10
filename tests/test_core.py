import json
import os
import tempfile
import unittest
from pathlib import Path

from roblox_vault import core


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_DATA_HOME"] = str(Path(self.tmp.name) / "data")
        os.environ["XDG_CONFIG_HOME"] = str(Path(self.tmp.name) / "config")

    def tearDown(self):
        self.tmp.cleanup()

    def test_project_scripts_and_gui(self):
        core.create_project("Inventory")
        self.assertEqual(core.list_projects(), ["Inventory"])
        core.create_script("Inventory", "server", "InventoryServer", "Script")
        core.create_script("Inventory", "shared", "ItemData", "ModuleScript")
        core.create_script("Inventory", "client", "InventoryUI", "LocalScript")
        core.create_gui("Inventory", "InventoryGui")
        files = core.list_files("Inventory")
        self.assertIn("src/server/InventoryServer.server.luau", files)
        self.assertIn("src/shared/ItemData.luau", files)
        self.assertIn("src/client/InventoryUI.client.luau", files)
        self.assertIn("src/gui/InventoryGui.model.json", files)
        self.assertEqual(files[0], "notes.md")

        proj = json.loads((core.project_path("Inventory") / "default.project.json").read_text())
        self.assertEqual(proj["tree"]["StarterGui"]["InventoryGui"]["$path"],
                         "src/gui/InventoryGui.model.json")
        core.delete_file("Inventory", "src/gui/InventoryGui.model.json")
        proj = json.loads((core.project_path("Inventory") / "default.project.json").read_text())
        self.assertNotIn("InventoryGui", proj["tree"]["StarterGui"])

    def test_version_suffixes_refused(self):
        core.create_project("Inventory")
        for bad in ("InventorySystemV3", "PlayerMovement_New", "Weapon_Final",
                    "Health_Updated", "Shop v2"):
            with self.assertRaises(core.VaultError):
                core.create_project(bad)
            with self.assertRaises(core.VaultError):
                core.create_script("Inventory", "server", bad, "Script")
            with self.assertRaises(core.VaultError):
                core.create_gui("Inventory", bad)
        for good in ("InventorySystem", "PlayerMovement", "Weapon", "Renew", "Player2"):
            core.create_script("Inventory", "shared", good, "ModuleScript")

    def test_uninstall_removes_legacy_install(self):
        home = Path(self.tmp.name) / "home"
        for rel in core.LEGACY_FILES + core.LEGACY_DATA:
            (home / rel).parent.mkdir(parents=True, exist_ok=True)
            (home / rel).write_text("x")
        for cmd in core.uninstall_commands(home):
            if cmd[0] == "rm":
                import subprocess
                subprocess.run(cmd, check=True)
        for rel in core.LEGACY_FILES + core.LEGACY_DATA:
            self.assertFalse((home / rel).exists(), rel)

    def test_read_write(self):
        core.create_project("A")
        core.write_file("A", "notes.md", "hello")
        self.assertEqual(core.read_file("A", "notes.md"), "hello")

    def test_rejects_bad_names_and_traversal(self):
        for bad in ("", "../x", "a/b", "x" * 70):
            with self.assertRaises(core.VaultError):
                core.create_project(bad)
        core.create_project("Safe")
        with self.assertRaises(core.VaultError):
            core.read_file("Safe", "../../../etc/passwd")
        with self.assertRaises(core.VaultError):
            core.create_project("Safe")  # duplicate

    def test_consent_versioned(self):
        s = core.Settings()
        self.assertFalse(s.has_consent)
        s.record_consent(True, True, True)
        self.assertTrue(core.Settings().has_consent)
        s.data["consent"]["version"] = "old"
        s.save()
        self.assertFalse(core.Settings().has_consent)

    def test_delete_all_data(self):
        core.create_project("X")
        core.Settings().record_consent(True, True, True)
        core.delete_all_data()
        self.assertFalse(core.data_dir().exists())
        self.assertFalse(core.config_dir().exists())

    def test_legal_pages_exist(self):
        legal = Path(core.__file__).parent / "legal"
        for key in ("privacy", "terms", "refund", "cookies", "third_party", "accessibility"):
            self.assertTrue((legal / f"{key}.md").read_text().strip())


if __name__ == "__main__":
    unittest.main()

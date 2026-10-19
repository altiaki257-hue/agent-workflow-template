import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from scripts import configure_notes as notes


class NoteConfigurationTests(unittest.TestCase):
    def test_repeat_setup_preserves_annotations_and_unrelated_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "vault"
            config = vault / ".obsidian"
            config.mkdir(parents=True)
            (config / "core-plugins.json").write_text(
                json.dumps({"sync": True, "graph": False}), encoding="utf-8"
            )
            with patch.object(
                notes.subprocess, "run", return_value=SimpleNamespace(stdout="a" * 40)
            ):
                notes.configure(vault, backup_root=Path(directory) / "backup")
                path = vault / notes.FOLDER / "Project brief.md"
                self.assertTrue(
                    path.read_text(encoding="utf-8").startswith("---\nproject:")
                )
                with path.open("a", encoding="utf-8") as stream:
                    stream.write("Owner annotation survives.\n")
                notes.configure(vault, backup_root=Path(directory) / "backup2")
            text = path.read_text(encoding="utf-8")
            self.assertEqual(1, text.count("Owner annotation survives."))
            self.assertEqual(1, text.count(notes.START))
            self.assertEqual(1, text.count("source_commit:"))
            data = json.loads(
                (config / "core-plugins.json").read_text(encoding="utf-8")
            )
            self.assertTrue(data["sync"])
            self.assertFalse(data["graph"])
            self.assertTrue(data["bases"])

    def test_existing_unowned_note_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.md"
            path.write_text("Personal content", encoding="utf-8")
            with self.assertRaises(ValueError):
                notes.managed_note(path, "Generated content")
            self.assertEqual("Personal content", path.read_text(encoding="utf-8"))

    def test_unsupported_metadata_is_preserved_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.md"
            for header in (
                "source: |\n  owner annotation",
                "source:\n  - owner annotation",
                "source:\n  nested: owner annotation",
                "'source': old",
                '"source": old',
                "source: old\nsource: duplicate",
            ):
                with self.subTest(header=header):
                    original = (
                        f"---\n{header}\n---\n\n{notes.START}\nold\n{notes.END}\n"
                    ).encode()
                    path.write_bytes(original)
                    with self.assertRaises(ValueError):
                        notes.managed_note(
                            path, "new", {"source": "https://example.org"}
                        )
                    self.assertEqual(original, path.read_bytes())

    def test_unsupported_settings_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "vault"
            config = vault / ".obsidian"
            config.mkdir(parents=True)
            path = config / "templates.json"
            original = b'["unexpected legacy shape"]\n'
            path.write_bytes(original)
            with self.assertRaises(ValueError):
                notes.configure(vault)
            self.assertEqual(original, path.read_bytes())

    def test_absolute_and_traversing_note_paths_cannot_escape_vault(self):
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "vault"
            vault.mkdir()
            for relative in (
                "../outside.md",
                str(Path(directory).resolve() / "outside.md"),
            ):
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    notes.safe_path(vault, relative)
            self.assertFalse((Path(directory) / "outside.md").exists())


if __name__ == "__main__":
    unittest.main()

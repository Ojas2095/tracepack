from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tracepack.cli import main
from tracepack.core import build_timeline, discover_evidence, parse_timestamp, write_case_pack


class TracePackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        (self.evidence / "notes.md").write_text(
            "# Review\n\n2025-04-02T08:30:00Z — Intake accepted.\n\n<script>not executable</script>\n",
            encoding="utf-8",
        )
        nested = self.evidence / "exports"
        nested.mkdir()
        (nested / "result.csv").write_text("id,status\n7,matched\n", encoding="utf-8")
        (self.evidence / "diagram.bin").write_bytes(b"\x89PNG\r\n\x00binary")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_discovery_is_sorted_and_hashes_source_bytes(self) -> None:
        items = discover_evidence(self.evidence)

        self.assertEqual([item.relative_path for item in items], ["diagram.bin", "exports/result.csv", "notes.md"])
        self.assertEqual(items[0].category, "Other")
        self.assertFalse(items[0].is_text)
        notes = items[-1]
        expected_hash = hashlib.sha256((self.evidence / "notes.md").read_bytes()).hexdigest()
        self.assertEqual(notes.sha256, expected_hash)
        self.assertTrue(notes.is_text)
        self.assertIn("2025-04-02T08:30:00Z", notes.date_tokens)

    def test_timeline_extracts_dated_lines_and_falls_back_for_binary(self) -> None:
        items = discover_evidence(self.evidence)
        timeline = build_timeline(items)

        self.assertEqual(len(timeline), 3)
        self.assertEqual(timeline[0].at, parse_timestamp("2025-04-02T08:30:00Z"))
        self.assertEqual(timeline[0].source, "notes.md")
        self.assertEqual({event.source for event in timeline[1:]}, {"diagram.bin", "exports/result.csv"})
        self.assertTrue(all("Evidence captured" == event.label for event in timeline[1:]))

    def test_build_writes_searchable_html_markdown_and_manifest(self) -> None:
        output = self.root / "pack"
        files = write_case_pack(self.evidence, output, "April review")

        self.assertEqual(set(files), {"html", "summary", "timeline", "manifest", "manifest_hash", "styles", "script"})
        self.assertTrue((output / "case_pack.html").exists())
        html = (output / "case_pack.html").read_text(encoding="utf-8")
        self.assertIn("April review", html)
        self.assertIn("id=\"search\"", html)
        self.assertIn("&lt;script&gt;not executable&lt;/script&gt;", html)
        self.assertNotIn("<script>not executable</script>", html)

        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_file_count"], 3)
        manifest_bytes = (output / "manifest.json").read_bytes()
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        self.assertTrue((output / "manifest.sha256").read_text(encoding="utf-8").startswith(manifest_hash))
        self.assertIn("April review", (output / "summary.md").read_text(encoding="utf-8"))
        self.assertIn("2025-04-02", (output / "timeline.md").read_text(encoding="utf-8"))

    def test_cli_rejects_non_empty_output_without_force(self) -> None:
        output = self.root / "pack"
        output.mkdir()
        (output / "keep.txt").write_text("do not replace", encoding="utf-8")

        result = main(["build", str(self.evidence), "--output", str(output)])

        self.assertEqual(result, 2)
        self.assertEqual((output / "keep.txt").read_text(encoding="utf-8"), "do not replace")


if __name__ == "__main__":
    unittest.main()

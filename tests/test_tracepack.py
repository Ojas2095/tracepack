from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tracepack.cli import main
from tracepack.core import build_timeline, discover_evidence, parse_timestamp, verify_case_pack, write_case_pack


class TracePackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        (self.evidence / "notes.md").write_text(
            "# Review\n\n2025-04-02T08:30:00Z — Intake accepted.\n2025-99-99 — malformed vendor token.\n\n<script>not executable</script>\n",
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
        self.assertIn('aria-label=\"Filter evidence\"', html)
        self.assertIn('aria-pressed=\"true\"', html)
        self.assertIn("&lt;script&gt;not executable&lt;/script&gt;", html)
        self.assertNotIn("<script>not executable</script>", html)

        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_file_count"], 3)
        manifest_bytes = (output / "manifest.json").read_bytes()
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        self.assertTrue((output / "manifest.sha256").read_text(encoding="utf-8").startswith(manifest_hash))
        self.assertIn("April review", (output / "summary.md").read_text(encoding="utf-8"))
        self.assertIn("2025-04-02", (output / "timeline.md").read_text(encoding="utf-8"))
        self.assertTrue((output / "evidence" / "exports" / "result.csv").exists())
        self.assertEqual(verify_case_pack(output), [])

    def test_build_rejects_overlapping_paths_without_deleting_evidence(self) -> None:
        sentinel = self.root / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        result = main(["build", str(self.evidence), "--output", str(self.root), "--force"])
        self.assertEqual(result, 2)
        self.assertTrue((self.evidence / "notes.md").exists())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_force_build_preserves_previous_output_when_discovery_fails(self) -> None:
        output = self.root / "pack"
        output.write_text("previous", encoding="utf-8")
        result = main(["build", str(self.evidence), "--output", str(output), "--force"])
        self.assertNotEqual(result, 0)
        self.assertEqual(output.read_text(encoding="utf-8"), "previous")

    def test_verify_detects_tampered_copied_source(self) -> None:
        output = self.root / "pack"
        write_case_pack(self.evidence, output, "April review")
        (output / "evidence" / "exports" / "result.csv").write_text("tampered", encoding="utf-8")
        self.assertIn("source checksum mismatch: exports/result.csv", verify_case_pack(output))

    def test_verify_rejects_malformed_manifest_without_crashing(self) -> None:
        output = self.root / "pack"
        output.mkdir()
        manifest = json.dumps({"files": None}).encode("utf-8")
        (output / "manifest.json").write_bytes(manifest)
        (output / "manifest.sha256").write_text(
            f"{hashlib.sha256(manifest).hexdigest()}  manifest.json\n",
            encoding="utf-8",
        )

        self.assertIn("manifest.json files must be a list", verify_case_pack(output))
        self.assertEqual(main(["verify", str(output)]), 2)

    def test_source_links_encode_url_special_characters(self) -> None:
        evidence = self.root / "special-evidence"
        evidence.mkdir()
        (evidence / "report #1.txt").write_text("hello", encoding="utf-8")
        output = self.root / "special-pack"

        write_case_pack(evidence, output, "Special paths")

        html = (output / "case_pack.html").read_text(encoding="utf-8")
        self.assertIn("evidence/report%20%231.txt", html)

    def test_cli_rejects_non_empty_output_without_force(self) -> None:
        output = self.root / "pack"
        output.mkdir()
        (output / "keep.txt").write_text("do not replace", encoding="utf-8")

        result = main(["build", str(self.evidence), "--output", str(output)])

        self.assertEqual(result, 2)
        self.assertEqual((output / "keep.txt").read_text(encoding="utf-8"), "do not replace")


if __name__ == "__main__":
    unittest.main()

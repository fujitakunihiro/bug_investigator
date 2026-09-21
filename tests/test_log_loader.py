import tempfile
import unittest
from pathlib import Path

from src.core.log_loader import LogLoadError, LogLoader


class LogLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.loader = LogLoader()

    def test_loads_lines_with_one_based_numbers_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "normal.log"
            original = "first\nsecond\n"
            path.write_text(original, encoding="utf-8")

            result = self.loader.load(path, "normal")

            self.assertEqual(
                [(line.line_number, line.raw_text, line.source) for line in result.lines],
                [(1, "first", "normal"), (2, "second", "normal")],
            )
            self.assertEqual(result.warnings, [])
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_replaces_invalid_utf8_and_returns_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.log"
            path.write_bytes(b"good\n\x80bad\n")

            result = self.loader.load(path, "abnormal")

            self.assertEqual(result.lines[1].raw_text, "�bad")
            self.assertEqual(len(result.warnings), 1)
            self.assertEqual(result.warnings[0].replacement_count, 1)

    def test_empty_file_returns_no_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.log"
            path.write_bytes(b"")

            result = self.loader.load(path, "normal")

            self.assertEqual(result.lines, [])
            self.assertEqual(result.warnings, [])

    def test_missing_file_raises_domain_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.log"

            with self.assertRaises(LogLoadError):
                self.loader.load(path, "normal")


if __name__ == "__main__":
    unittest.main()

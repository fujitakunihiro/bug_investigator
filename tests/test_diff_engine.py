import unittest

from src.core.diff_engine import DiffEngine, DiffType
from src.core.log_loader import LogLine
from src.core.normalizer import Normalizer


def normalized_lines(texts: list[str], source: str):
    lines = [LogLine(index, text, source) for index, text in enumerate(texts, start=1)]
    return Normalizer([]).normalize(lines)


class DiffEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DiffEngine()

    def test_detects_missing_clock_ready_from_phase0_data(self) -> None:
        normal = normalized_lines(
            ["PowerOn", "ClockStart", "ClockReady", "PanelInit", "DisplayStart"],
            "normal",
        )
        abnormal = normalized_lines(
            ["PowerOn", "ClockStart", "PanelInit", "DisplayStart"],
            "abnormal",
        )

        result = self.engine.compare(normal, abnormal)

        self.assertEqual(result.missing_count, 1)
        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.changed_count, 0)
        self.assertEqual(result.items[0].type, DiffType.MISSING)
        self.assertEqual(result.items[0].normal_line.normalized_text, "ClockReady")
        self.assertEqual(result.items[0].normal_index, 2)

    def test_detects_added_line(self) -> None:
        normal = normalized_lines(["A", "C"], "normal")
        abnormal = normalized_lines(["A", "B", "C"], "abnormal")

        result = self.engine.compare(normal, abnormal)

        self.assertEqual([item.type for item in result.items], [DiffType.ADDED])
        self.assertEqual(result.items[0].abnormal_line.normalized_text, "B")

    def test_detects_changed_line(self) -> None:
        normal = normalized_lines(["A", "B", "C"], "normal")
        abnormal = normalized_lines(["A", "X", "C"], "abnormal")

        result = self.engine.compare(normal, abnormal)

        self.assertEqual([item.type for item in result.items], [DiffType.CHANGED])
        self.assertEqual(result.items[0].normal_line.normalized_text, "B")
        self.assertEqual(result.items[0].abnormal_line.normalized_text, "X")

    def test_identical_logs_have_no_differences(self) -> None:
        lines = ["A", "B"]

        result = self.engine.compare(
            normalized_lines(lines, "normal"),
            normalized_lines(lines, "abnormal"),
        )

        self.assertEqual(result.items, [])
        self.assertEqual(result.missing_count, 0)
        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.changed_count, 0)

    def test_replace_with_different_lengths_keeps_nearby_pairing(self) -> None:
        normal = normalized_lines(["A", "B", "C"], "normal")
        abnormal = normalized_lines(["A", "X", "Y", "C"], "abnormal")

        result = self.engine.compare(normal, abnormal)

        self.assertEqual(
            [item.type for item in result.items],
            [DiffType.CHANGED, DiffType.ADDED],
        )
        self.assertEqual(result.items[0].normal_line.normalized_text, "B")
        self.assertEqual(result.items[0].abnormal_line.normalized_text, "X")
        self.assertEqual(result.items[1].abnormal_line.normalized_text, "Y")

    def test_detects_multiple_missing_lines_in_order(self) -> None:
        normal = normalized_lines(["A", "B", "C", "D"], "normal")
        abnormal = normalized_lines(["A", "D"], "abnormal")

        result = self.engine.compare(normal, abnormal)

        self.assertEqual(
            [item.normal_line.normalized_text for item in result.items],
            ["B", "C"],
        )
        self.assertEqual(result.missing_count, 2)

    def test_counts_each_difference_category_independently(self) -> None:
        normal = normalized_lines(["A", "B", "C"], "normal")
        abnormal = normalized_lines(["A", "X", "Y", "C", "Z"], "abnormal")

        result = self.engine.compare(normal, abnormal)

        self.assertEqual(result.changed_count, 1)
        self.assertEqual(result.added_count, 2)
        self.assertEqual(result.missing_count, 0)


if __name__ == "__main__":
    unittest.main()

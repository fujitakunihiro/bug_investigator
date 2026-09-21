import unittest

from src.core.diff_engine import DiffEngine, DiffType
from src.core.divergence import DivergenceDetector
from src.core.log_loader import LogLine
from src.core.normalizer import Normalizer


def normalized_lines(texts: list[str], source: str):
    return Normalizer([]).normalize(
        [LogLine(index, text, source) for index, text in enumerate(texts, start=1)]
    )


class DivergenceDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DiffEngine()
        self.detector = DivergenceDetector(context_radius=20)

    def test_finds_first_missing_clock_ready_with_previous_and_next(self) -> None:
        normal = normalized_lines(
            ["PowerOn", "ClockStart", "ClockReady", "PanelInit", "DisplayStart"],
            "normal",
        )
        abnormal = normalized_lines(
            ["PowerOn", "ClockStart", "PanelInit", "DisplayStart"],
            "abnormal",
        )

        result = self.detector.detect(self.engine.compare(normal, abnormal), normal, abnormal)

        self.assertTrue(result.found)
        self.assertEqual(result.type, DiffType.MISSING)
        self.assertEqual(result.expected.normalized_text, "ClockReady")
        self.assertIsNone(result.observed)
        self.assertEqual(result.previous.normalized_text, "ClockStart")
        self.assertEqual(result.next.normalized_text, "PanelInit")
        self.assertEqual(result.normal_context.focus_index, 2)
        self.assertIsNone(result.abnormal_context.focus_index)
        self.assertEqual(len(result.normal_context.lines), 5)
        self.assertEqual(len(result.abnormal_context.lines), 4)

    def test_changed_and_added_use_the_observed_side_for_neighbors(self) -> None:
        normal = normalized_lines(["A", "B", "C"], "normal")
        abnormal = normalized_lines(["A", "X", "C"], "abnormal")

        result = self.detector.detect(self.engine.compare(normal, abnormal), normal, abnormal)

        self.assertEqual(result.type, DiffType.CHANGED)
        self.assertEqual(result.expected.normalized_text, "B")
        self.assertEqual(result.observed.normalized_text, "X")
        self.assertEqual(result.previous.normalized_text, "A")
        self.assertEqual(result.next.normalized_text, "C")

    def test_no_difference_returns_empty_result(self) -> None:
        normal = normalized_lines(["A", "B"], "normal")
        abnormal = normalized_lines(["A", "B"], "abnormal")

        result = self.detector.detect(self.engine.compare(normal, abnormal), normal, abnormal)

        self.assertFalse(result.found)
        self.assertIsNone(result.type)
        self.assertEqual(result.normal_context.lines, [])
        self.assertEqual(result.abnormal_context.lines, [])

    def test_context_is_limited_to_requested_radius(self) -> None:
        normal = normalized_lines([f"E{i}" for i in range(10)], "normal")
        abnormal = normalized_lines([f"E{i}" for i in range(5)] + ["X"] + [f"E{i}" for i in range(6, 10)], "abnormal")
        detector = DivergenceDetector(context_radius=2)

        result = detector.detect(self.engine.compare(normal, abnormal), normal, abnormal)

        self.assertEqual([line.normalized_text for line in result.normal_context.lines], ["E3", "E4", "E5", "E6", "E7"])
        self.assertEqual([line.normalized_text for line in result.abnormal_context.lines], ["E3", "E4", "X", "E6", "E7"])

    def test_first_difference_wins_over_later_differences(self) -> None:
        normal = normalized_lines(["A", "B", "C", "D"], "normal")
        abnormal = normalized_lines(["A", "X", "C", "Y"], "abnormal")

        result = self.detector.detect(self.engine.compare(normal, abnormal), normal, abnormal)

        self.assertEqual(result.type, DiffType.CHANGED)
        self.assertEqual(result.expected.normalized_text, "B")
        self.assertEqual(result.observed.normalized_text, "X")

    def test_first_line_has_no_previous_and_last_line_has_no_next(self) -> None:
        normal = normalized_lines(["A", "B"], "normal")
        abnormal = normalized_lines(["X", "B"], "abnormal")

        first = self.detector.detect(self.engine.compare(normal, abnormal), normal, abnormal)
        self.assertIsNone(first.previous)
        self.assertEqual(first.next.normalized_text, "B")

        normal = normalized_lines(["A", "B", "C"], "normal")
        abnormal = normalized_lines(["A", "B"], "abnormal")
        last = self.detector.detect(self.engine.compare(normal, abnormal), normal, abnormal)
        self.assertEqual(last.expected.normalized_text, "C")
        self.assertEqual(last.previous.normalized_text, "B")
        self.assertIsNone(last.next)

    def test_empty_side_still_returns_a_found_divergence(self) -> None:
        normal = normalized_lines(["A"], "normal")
        abnormal = normalized_lines([], "abnormal")

        result = self.detector.detect(self.engine.compare(normal, abnormal), normal, abnormal)

        self.assertTrue(result.found)
        self.assertEqual(result.type, DiffType.MISSING)
        self.assertEqual(result.expected.normalized_text, "A")
        self.assertEqual(result.normal_context.lines[0].normalized_text, "A")
        self.assertEqual(result.abnormal_context.lines, [])


if __name__ == "__main__":
    unittest.main()

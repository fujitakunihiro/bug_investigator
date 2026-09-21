import tempfile
import unittest
from pathlib import Path

from src.core.log_loader import LogLine
from src.core.normalizer import NormalizationConfigError, NormalizationRule, Normalizer


class NormalizerTests(unittest.TestCase):
    def test_default_rules_normalize_timestamp_and_address(self) -> None:
        normalizer = Normalizer.default()
        lines = [
            LogLine(
                line_number=1,
                raw_text="12:31:20.123 PanelOpen id=123 addr=0x1234",
                source="normal",
            ),
            LogLine(
                line_number=1,
                raw_text="12:32:10.456 PanelOpen id=456 addr=0xABCD",
                source="abnormal",
            ),
        ]

        normalized = normalizer.normalize(lines)

        self.assertEqual(
            normalized[0].normalized_text,
            "<TIMESTAMP> PanelOpen id=123 addr=<ADDR>",
        )
        self.assertEqual(
            normalized[1].normalized_text,
            "<TIMESTAMP> PanelOpen id=456 addr=<ADDR>",
        )
        self.assertEqual(normalized[0].raw_text, lines[0].raw_text)

    def test_custom_json_rule_is_applied_after_default_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "normalization.json"
            path.write_text(
                '{"rules": [{"name": "id", "pattern": "id=\\\\d+", '
                '"replacement": "id=<ID>"}]}',
                encoding="utf-8",
            )
            normalizer = Normalizer.from_config(path)
            line = LogLine(1, "PanelOpen id=123", "normal")

            result = normalizer.normalize_line(line)

            self.assertEqual(result.normalized_text, "PanelOpen id=<ID>")

    def test_invalid_config_raises_domain_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text('{"rules": [{"name": "bad", "pattern": "["}]}', encoding="utf-8")

            with self.assertRaises(NormalizationConfigError):
                Normalizer.from_config(path)

    def test_rules_are_applied_in_order(self) -> None:
        normalizer = Normalizer(
            [
                NormalizationRule.create("first", "foo", "bar"),
                NormalizationRule.create("second", "bar", "baz"),
            ]
        )
        line = LogLine(1, "foo", "normal")

        self.assertEqual(normalizer.normalize_line(line).normalized_text, "baz")

    def test_timestamp_rule_accepts_comma_and_six_fraction_digits(self) -> None:
        normalizer = Normalizer.default()
        lines = [
            LogLine(1, "12:31:20,123456 Event", "normal"),
            LogLine(2, "12:31:20 Event", "normal"),
        ]

        normalized = normalizer.normalize(lines)

        self.assertEqual(normalized[0].normalized_text, "<TIMESTAMP> Event")
        self.assertEqual(normalized[1].normalized_text, "<TIMESTAMP> Event")

    def test_hex_rule_is_case_insensitive_for_digits_and_prefix(self) -> None:
        normalizer = Normalizer.default()
        line = LogLine(1, "addr=0XAbCd value=0x00ff", "normal")

        result = normalizer.normalize_line(line)

        self.assertEqual(result.normalized_text, "addr=<ADDR> value=<ADDR>")

    def test_non_matching_text_is_preserved(self) -> None:
        normalizer = Normalizer.default()
        line = LogLine(1, "No dynamic values here", "normal")

        result = normalizer.normalize_line(line)

        self.assertEqual(result.normalized_text, line.raw_text)


if __name__ == "__main__":
    unittest.main()

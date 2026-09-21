"""Configurable log-line normalization for comparison."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .log_loader import LogLine


@dataclass(frozen=True)
class NormalizationRule:
    """One regular-expression replacement applied to a log line."""

    name: str
    pattern: str
    replacement: str
    _compiled: re.Pattern[str]

    @classmethod
    def create(cls, name: str, pattern: str, replacement: str) -> "NormalizationRule":
        if not name:
            raise ValueError("正規化ルール名は空にできません")
        if not pattern:
            raise ValueError(f"正規化ルールの正規表現が空です: {name}")
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"正規化ルールの正規表現が不正です: {name}") from exc
        return cls(name, pattern, replacement, compiled)

    def apply(self, text: str) -> str:
        return self._compiled.sub(self.replacement, text)


@dataclass(frozen=True)
class NormalizedLine:
    """A source line with its comparison representation."""

    line_number: int
    raw_text: str
    normalized_text: str
    source: str


class NormalizationConfigError(ValueError):
    """Raised when a normalization configuration cannot be used."""


class Normalizer:
    """Apply ordered regular-expression rules to loaded log lines."""

    def __init__(self, rules: Iterable[NormalizationRule]) -> None:
        self.rules = tuple(rules)

    @classmethod
    def from_config(cls, path: str | Path) -> "Normalizer":
        config_path = Path(path)
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                payload: Any = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise NormalizationConfigError(
                f"正規化設定を読み込めません: {config_path}"
            ) from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("rules"), list):
            raise NormalizationConfigError("正規化設定には rules 配列が必要です")

        rules: list[NormalizationRule] = []
        for index, item in enumerate(payload["rules"]):
            if not isinstance(item, dict):
                raise NormalizationConfigError(
                    f"正規化ルールがオブジェクトではありません: index={index}"
                )
            try:
                name = item["name"]
                pattern = item["pattern"]
                replacement = item["replacement"]
                if not all(isinstance(value, str) for value in (name, pattern, replacement)):
                    raise TypeError
                rules.append(NormalizationRule.create(name, pattern, replacement))
            except (KeyError, TypeError, ValueError) as exc:
                raise NormalizationConfigError(
                    f"正規化ルールが不正です: index={index}"
                ) from exc
        return cls(rules)

    @classmethod
    def default(cls) -> "Normalizer":
        config_path = Path(__file__).parents[1] / "config" / "normalization.json"
        return cls.from_config(config_path)

    def normalize_line(self, line: LogLine) -> NormalizedLine:
        normalized_text = line.raw_text
        for rule in self.rules:
            normalized_text = rule.apply(normalized_text)
        return NormalizedLine(
            line_number=line.line_number,
            raw_text=line.raw_text,
            normalized_text=normalized_text,
            source=line.source,
        )

    def normalize(self, lines: Iterable[LogLine]) -> list[NormalizedLine]:
        return [self.normalize_line(line) for line in lines]

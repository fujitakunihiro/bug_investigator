"""Read-only text log loading for the Bug Investigator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


LogSource = Literal["normal", "abnormal"]


@dataclass(frozen=True)
class LogLine:
    """A single source-log line with its original location and text."""

    line_number: int
    raw_text: str
    source: LogSource


@dataclass(frozen=True)
class LoadWarning:
    """A recoverable issue found while loading a log."""

    message: str
    replacement_count: int = 0


@dataclass(frozen=True)
class LogLoadResult:
    """Loaded lines and non-fatal warnings for one log file."""

    path: Path
    lines: list[LogLine]
    warnings: list[LoadWarning]


class LogLoadError(RuntimeError):
    """Raised when a log cannot be opened or read."""


class LogLoader:
    """Load a text log without modifying the source file."""

    def load(self, path: str | Path, source: LogSource) -> LogLoadResult:
        """Load *path* and assign every line the supplied source label."""

        log_path = Path(path)
        lines: list[LogLine] = []
        replacement_count = 0
        try:
            with log_path.open(
                "r", encoding="utf-8", errors="replace", newline=""
            ) as handle:
                for index, line in enumerate(handle, start=1):
                    raw_text = line.rstrip("\r\n")
                    replacement_count += raw_text.count("\ufffd")
                    lines.append(
                        LogLine(
                            line_number=index,
                            raw_text=raw_text,
                            source=source,
                        )
                    )
        except (OSError, ValueError) as exc:
            raise LogLoadError(f"ログを読み込めません: {log_path}") from exc

        warnings: list[LoadWarning] = []
        if replacement_count:
            warnings.append(
                LoadWarning(
                    message=(
                        f"UTF-8として解釈できないバイトを"
                        f" {replacement_count} 箇所置換しました: {log_path}"
                    ),
                    replacement_count=replacement_count,
                )
            )

        return LogLoadResult(path=log_path, lines=lines, warnings=warnings)

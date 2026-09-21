"""FIRST DIVERGENCE detection and surrounding context extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .diff_engine import DiffItem, DiffResult, DiffType
from .normalizer import NormalizedLine


@dataclass(frozen=True)
class ContextWindow:
    """A bounded view of one normalized log around a divergence."""

    lines: list[NormalizedLine]
    focus_index: int | None
    start_line_number: int | None
    end_line_number: int | None


@dataclass(frozen=True)
class FirstDivergence:
    """The first ordered difference and its investigation context."""

    found: bool
    type: DiffType | None
    expected: NormalizedLine | None
    observed: NormalizedLine | None
    previous: NormalizedLine | None
    next: NormalizedLine | None
    normal_context: ContextWindow
    abnormal_context: ContextWindow


class DivergenceDetector:
    """Select the first diff and build context windows for both logs."""

    def __init__(self, context_radius: int = 20) -> None:
        if context_radius < 0:
            raise ValueError("context_radius は0以上で指定してください")
        self.context_radius = context_radius

    def detect(
        self,
        diff_result: DiffResult,
        normal_lines: Sequence[NormalizedLine],
        abnormal_lines: Sequence[NormalizedLine],
    ) -> FirstDivergence:
        if not diff_result.items:
            return FirstDivergence(
                found=False,
                type=None,
                expected=None,
                observed=None,
                previous=None,
                next=None,
                normal_context=self._empty_context(),
                abnormal_context=self._empty_context(),
            )

        item = diff_result.items[0]
        normal_anchor = self._anchor(item, side="normal", length=len(normal_lines))
        abnormal_anchor = self._anchor(item, side="abnormal", length=len(abnormal_lines))
        normal_context = self._context(normal_lines, normal_anchor, item.normal_line)
        abnormal_context = self._context(
            abnormal_lines, abnormal_anchor, item.abnormal_line
        )

        if item.type is DiffType.MISSING:
            expected = item.normal_line
            observed = None
            previous = self._at(normal_lines, (normal_anchor or 0) - 1)
            following = self._at(normal_lines, (normal_anchor or 0) + 1)
        elif item.type is DiffType.ADDED:
            expected = None
            observed = item.abnormal_line
            previous = self._at(abnormal_lines, (abnormal_anchor or 0) - 1)
            following = self._at(abnormal_lines, (abnormal_anchor or 0) + 1)
        else:
            expected = item.normal_line
            observed = item.abnormal_line
            previous = self._at(normal_lines, (normal_anchor or 0) - 1)
            following = self._at(normal_lines, (normal_anchor or 0) + 1)

        return FirstDivergence(
            found=True,
            type=item.type,
            expected=expected,
            observed=observed,
            previous=previous,
            next=following,
            normal_context=normal_context,
            abnormal_context=abnormal_context,
        )

    def _anchor(
        self, item: DiffItem, *, side: str, length: int
    ) -> int | None:
        index = item.normal_index if side == "normal" else item.abnormal_index
        if index is not None:
            return min(max(index, 0), length)
        other_index = item.abnormal_index if side == "normal" else item.normal_index
        if other_index is None:
            return None
        return min(max(other_index, 0), length)

    def _context(
        self,
        lines: Sequence[NormalizedLine],
        anchor: int | None,
        focus: NormalizedLine | None,
    ) -> ContextWindow:
        if not lines:
            return self._empty_context()
        position = min(max(anchor if anchor is not None else 0, 0), len(lines) - 1)
        start = max(0, position - self.context_radius)
        end = min(len(lines), position + self.context_radius + 1)
        window = list(lines[start:end])
        focus_index = None
        if focus is not None and start <= position < end:
            focus_index = position - start
        return ContextWindow(
            lines=window,
            focus_index=focus_index,
            start_line_number=window[0].line_number,
            end_line_number=window[-1].line_number,
        )

    @staticmethod
    def _at(lines: Sequence[NormalizedLine], index: int) -> NormalizedLine | None:
        if 0 <= index < len(lines):
            return lines[index]
        return None

    @staticmethod
    def _empty_context() -> ContextWindow:
        return ContextWindow(
            lines=[],
            focus_index=None,
            start_line_number=None,
            end_line_number=None,
        )

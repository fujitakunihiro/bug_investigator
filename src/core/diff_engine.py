"""Ordered comparison of normalized normal and abnormal logs."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from typing import Sequence

from .normalizer import NormalizedLine


class DiffType(str, Enum):
    """The V1 categories of observable log differences."""

    MISSING = "MISSING"
    ADDED = "ADDED"
    CHANGED = "CHANGED"


@dataclass(frozen=True)
class DiffItem:
    """One ordered difference between the two normalized logs."""

    type: DiffType
    normal_line: NormalizedLine | None
    abnormal_line: NormalizedLine | None
    normal_index: int | None
    abnormal_index: int | None


@dataclass(frozen=True)
class DiffResult:
    """All differences and their counts, in chronological order."""

    items: list[DiffItem]

    @property
    def missing_count(self) -> int:
        return sum(item.type is DiffType.MISSING for item in self.items)

    @property
    def added_count(self) -> int:
        return sum(item.type is DiffType.ADDED for item in self.items)

    @property
    def changed_count(self) -> int:
        return sum(item.type is DiffType.CHANGED for item in self.items)


class DiffEngine:
    """Compare normalized log sequences while retaining source locations."""

    def compare(
        self,
        normal_lines: Sequence[NormalizedLine],
        abnormal_lines: Sequence[NormalizedLine],
    ) -> DiffResult:
        matcher = SequenceMatcher(
            a=[line.normalized_text for line in normal_lines],
            b=[line.normalized_text for line in abnormal_lines],
            autojunk=False,
        )
        items: list[DiffItem] = []

        for tag, normal_start, normal_end, abnormal_start, abnormal_end in matcher.get_opcodes():
            if tag in ("equal",):
                continue
            if tag == "delete":
                items.extend(
                    DiffItem(
                        type=DiffType.MISSING,
                        normal_line=normal_lines[index],
                        abnormal_line=None,
                        normal_index=index,
                        abnormal_index=None,
                    )
                    for index in range(normal_start, normal_end)
                )
                continue
            if tag == "insert":
                items.extend(
                    DiffItem(
                        type=DiffType.ADDED,
                        normal_line=None,
                        abnormal_line=abnormal_lines[index],
                        normal_index=None,
                        abnormal_index=index,
                    )
                    for index in range(abnormal_start, abnormal_end)
                )
                continue

            # A replace block describes nearby lines on both sides. Pair the
            # overlapping part as Changed, then classify any remainder.
            normal_count = normal_end - normal_start
            abnormal_count = abnormal_end - abnormal_start
            paired_count = min(normal_count, abnormal_count)
            items.extend(
                DiffItem(
                    type=DiffType.CHANGED,
                    normal_line=normal_lines[normal_start + offset],
                    abnormal_line=abnormal_lines[abnormal_start + offset],
                    normal_index=normal_start + offset,
                    abnormal_index=abnormal_start + offset,
                )
                for offset in range(paired_count)
            )
            items.extend(
                DiffItem(
                    type=DiffType.MISSING,
                    normal_line=normal_lines[index],
                    abnormal_line=None,
                    normal_index=index,
                    abnormal_index=None,
                )
                for index in range(normal_start + paired_count, normal_end)
            )
            items.extend(
                DiffItem(
                    type=DiffType.ADDED,
                    normal_line=None,
                    abnormal_line=abnormal_lines[index],
                    normal_index=None,
                    abnormal_index=index,
                )
                for index in range(abnormal_start + paired_count, abnormal_end)
            )

        return DiffResult(items=items)

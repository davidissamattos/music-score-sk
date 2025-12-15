"""Utilities for extracting measures and parts from scores."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import BinaryIO, Iterable

from music21 import stream as m21_stream

from .utils import infer_format_from_path, load_score, write_score


def extract_sections(
    *,
    source: str | None = None,
    output: str | None = None,
    output_format: str | None = None,
    measures: str | None = None,
    part_names: str | None = None,
    part_numbers: str | None = None,
    stdin_data: bytes | None = None,
    stdout_buffer: BinaryIO | None = None,
) -> str:
    """Extract selected measures/parts from a score and persist the result."""
    score = load_score(source, stdin_data=stdin_data)
    ranges = _parse_measure_spec(measures)
    selected_parts = _select_parts(score, part_names=part_names, part_numbers=part_numbers)

    parts_to_add = []
    if not ranges:
        parts_to_add = [copy.deepcopy(part) for part in selected_parts]
    else:
        for part in selected_parts:
            shortened = _slice_part(part, ranges)
            if shortened is not None:
                parts_to_add.append(shortened)

    new_score = m21_stream.Score()
    if score.metadata:
        try:
            new_score.metadata = score.metadata.clone()
        except Exception:
            new_score.metadata = score.metadata

    if not parts_to_add and not list(score.parts):
        # Handle scores without explicit parts; slice the score itself.
        base = _slice_part(score, ranges) if ranges else copy.deepcopy(score)
        if base:
            parts_to_add.append(base)

    for part in parts_to_add:
        new_score.insert(len(new_score.parts), part)

    final_format = output_format or infer_format_from_path(output, default=infer_format_from_path(source))
    return write_score(
        new_score,
        final_format,
        output=output,
        stdout_buffer=stdout_buffer,
    )


def _parse_measure_spec(spec: str | None) -> list[tuple[int, int]]:
    if not spec:
        return []
    ranges: list[tuple[int, int]] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_str, end_str = token.split("-", 1)
            start = int(start_str)
            end = int(end_str)
        else:
            start = end = int(token)
        if start > end:
            start, end = end, start
        ranges.append((start, end))
    return ranges


def _select_parts(
    score: m21_stream.Score,
    *,
    part_names: str | None,
    part_numbers: str | None,
) -> list[m21_stream.Stream]:
    parts = list(score.parts)
    if not parts:
        return [score]

    name_set = _parse_csv(part_names, lower=True)
    number_set = set(int(value) for value in _parse_csv(part_numbers) if value.isdigit())

    if not name_set and not number_set:
        return parts

    selected: list[m21_stream.Stream] = []
    for idx, part in enumerate(parts, start=1):
        match = False
        if name_set:
            part_name = (part.partName or "").lower()
            part_id = (part.id or "").lower()
            if part_name in name_set or part_id in name_set:
                match = True
        if number_set and idx in number_set:
            match = True
        if match:
            selected.append(part)

    if not selected:
        available = ", ".join(
            filter(
                None,
                [(p.partName or p.id or f"Part {i+1}") for i, p in enumerate(parts)],
            )
        )
        raise ValueError(f"No parts matched the selection. Available parts: {available}")
    return selected


def _parse_csv(value: str | None, *, lower: bool = False) -> list[str]:
    if not value:
        return []
    tokens = [item.strip() for item in value.split(",") if item.strip()]
    if lower:
        tokens = [token.lower() for token in tokens]
    return tokens


def _slice_part(part: m21_stream.Stream, ranges: Iterable[tuple[int, int]]) -> m21_stream.Part | None:
    new_part = m21_stream.Part()
    part_id = getattr(part, "id", None)
    if not isinstance(part_id, str) or part_id.isdigit():
        part_id = None
    new_part.id = part_id if part_id else "extracted-part"
    if hasattr(part, "partName"):
        new_part.partName = getattr(part, "partName", None)

    for start, end in ranges:
        segment = part.measures(start, end)
        if segment is None:
            continue
        for element in segment:
            new_part.append(copy.deepcopy(element))

    return new_part if len(new_part) > 0 else None

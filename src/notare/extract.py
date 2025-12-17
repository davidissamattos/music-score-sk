"""Utilities for extracting measures and parts from scores."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import BinaryIO, Iterable

from music21 import stream as m21_stream

from .utils import load_score, write_score
from .utils import _renumber_measures_starting_at_one, _parse_measure_spec, _select_parts


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
    measures = str(measures).strip() if measures else None
    part_names = str(part_names).strip() if part_names else None
    part_numbers = str(part_numbers).strip() if part_numbers else None
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

    # Renumber measures to start from 1 in the extracted score
    _renumber_measures_starting_at_one(new_score)

    # Normalize notation for export
    try:
        new_score.makeNotation()
    except Exception:
        pass

    message = write_score(
        new_score,
        target_format=output_format,
        output=output,
        stdout_buffer=stdout_buffer,
    )
    return message



    


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

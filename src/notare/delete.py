"""Utilities for deleting measures and parts from scores.

This module mirrors the `extract` module's interface but performs deletions:
- Remove selected measures across parts
- Remove selected parts by name or number

Behavior
- Measure numbering is normalized to start at 1 on import and renumbered
  again after deletions so the final score counts from 1 consecutively.
- Metadata is preserved from the source score.
"""

from __future__ import annotations

import copy
from typing import BinaryIO, Iterable

from music21 import stream as m21_stream
from music21 import meter as m21_meter
from music21 import key as m21_key
from music21 import clef as m21_clef

from .utils import load_score, write_score, _renumber_measures_starting_at_one
from .utils import _parse_measure_spec, _select_parts


def delete_sections(
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
    """Delete selected measures and/or parts from a score and persist the result.

    Args
    - measures: Comma-separated indices and ranges, e.g., `1,3,5-8`. Numbers refer to
      normalized measure indices starting at 1 (pickup is considered 1). When provided,
      the specified measures are removed from all remaining parts.
    - part_names: Comma-separated part names/ids to delete
    - part_numbers: Comma-separated part numbers (1-based) to delete

    Returns
    - Message from `write_score` if writing to a file, otherwise empty string when streaming to stdout.
    """
    score = load_score(source, stdin_data=stdin_data)
    measures = str(measures).strip() if measures else None
    part_names = str(part_names).strip() if part_names else None
    part_numbers = str(part_numbers).strip() if part_numbers else None

    # Build delete ranges
    ranges = _parse_measure_spec(measures)

    # Determine parts to keep (complement of selected for deletion)
    all_parts = list(score.parts) or [score]
    # Only delete parts that actually exist; if selection matches none, delete none
    if part_names or part_numbers:
        try:
            selected = _select_parts(score, part_names=part_names, part_numbers=part_numbers)
        except ValueError:
            selected = []
        to_delete = set(selected)
    else:
        to_delete = set()

    parts_to_keep: list[m21_stream.Stream] = [p for p in all_parts if p not in to_delete]

    new_score = m21_stream.Score()
    if score.metadata:
        try:
            new_score.metadata = score.metadata.clone()
        except Exception:
            new_score.metadata = score.metadata

    # If no explicit parts exist (single stream score), operate directly
    if not list(score.parts):
        kept_stream = _delete_measures_from_stream(score, ranges) if ranges else copy.deepcopy(score)
        if kept_stream:
            new_score.insert(0, kept_stream)
    else:
        for part in parts_to_keep:
            kept_part = _delete_measures_from_stream(part, ranges) if ranges else copy.deepcopy(part)
            if kept_part:
                new_score.insert(len(new_score.parts), kept_part)

    # If after deletions there are no parts at all, add a default part with a single empty measure
    if not list(new_score.parts):
        fallback_part = m21_stream.Part(id="P1")
        try:
            fallback_part.partName = "Part 1"
        except Exception:
            pass
        empty_meas = m21_stream.Measure(number=1)
        try:
            fallback_part.append(empty_meas)
        except Exception:
            pass
        new_score.insert(0, fallback_part)

    # Renumber measures to start from 1 consecutively
    _renumber_measures_starting_at_one(new_score)

    # Normalize notational representation to avoid inexpressible durations on export
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


def _delete_measures_from_stream(
    part: m21_stream.Stream,
    ranges: Iterable[tuple[int, int]],
) -> m21_stream.Part | m21_stream.Stream | None:
    """Return a new stream with measures outside the delete ranges preserved.

    Operates on a part or score stream. Copies metadata-like identifiers when available.
    """
    # Build set of measure numbers to delete
    delete_set: set[int] = set()
    for start, end in ranges:
        if start > end:
            start, end = end, start
        delete_set.update(range(start, end + 1))

    # Create a new Part or Stream depending on input
    if isinstance(part, m21_stream.Part):
        new_part = m21_stream.Part()
        part_id = getattr(part, "id", None)
        if not isinstance(part_id, str) or (isinstance(part_id, str) and part_id.isdigit()):
            part_id = None
        new_part.id = part_id if part_id else "part"
        if hasattr(part, "partName"):
            new_part.partName = getattr(part, "partName", None)

        kept_measures: list[m21_stream.Measure] = []
        first_kept_num: int | None = None
        for meas in part.getElementsByClass(m21_stream.Measure):
            try:
                num = int(getattr(meas, "number", 0) or 0)
            except Exception:
                num = 0
            if num not in delete_set:
                if first_kept_num is None:
                    first_kept_num = num
                kept_measures.append(copy.deepcopy(meas))

        if not kept_measures:
            # All measures got deleted or none existed; keep part with a single empty measure
            empty_measure = m21_stream.Measure(number=1)
            try:
                new_part.append(empty_measure)
            except Exception:
                pass
            return new_part

        _insert_starting_attributes(kept_measures[0], part, first_kept_num)
        for meas in kept_measures:
            new_part.append(meas)
        return new_part

    # Generic stream (e.g., score without explicit parts)
    new_stream = m21_stream.Stream()
    kept_measures: list[m21_stream.Measure] = []
    first_kept_num: int | None = None
    for meas in part.getElementsByClass(m21_stream.Measure):
        try:
            num = int(getattr(meas, "number", 0) or 0)
        except Exception:
            num = 0
        if num not in delete_set:
            if first_kept_num is None:
                first_kept_num = num
            kept_measures.append(copy.deepcopy(meas))
    if not kept_measures:
        # Preserve stream with a single empty measure if all were deleted
        empty_measure = m21_stream.Measure(number=1)
        try:
            new_stream.append(empty_measure)
        except Exception:
            pass
        return new_stream
    _insert_starting_attributes(kept_measures[0], part, first_kept_num)
    for meas in kept_measures:
        new_stream.append(meas)
    return new_stream


def _insert_starting_attributes(
    first_measure: m21_stream.Measure,
    original: m21_stream.Stream,
    first_kept_num: int | None,
) -> None:
    """Insert starting clef, time signature, and key signature into the first kept measure.

    If the first kept measure is not 1, we look back in the original stream for the
    latest attributes prior to `first_kept_num` and insert copies into the first measure.
    """
    if not first_kept_num or first_kept_num <= 1:
        return

    last_ts = None
    last_key = None
    last_clef = None

    for meas in original.getElementsByClass(m21_stream.Measure):
        try:
            num = int(getattr(meas, "number", 0) or 0)
        except Exception:
            num = 0
        if num >= first_kept_num:
            break
        # Search within measure for attributes; keep latest
        ts = meas.getElementsByClass(m21_meter.TimeSignature)
        if ts:
            last_ts = ts[-1]
        ks = meas.getElementsByClass(m21_key.KeySignature)
        if ks:
            last_key = ks[-1]
        cf = meas.getElementsByClass(m21_clef.Clef)
        if cf:
            last_clef = cf[-1]

    if last_clef is not None:
        try:
            first_measure.insert(0, copy.deepcopy(last_clef))
        except Exception:
            pass
    if last_key is not None:
        try:
            first_measure.insert(0, copy.deepcopy(last_key))
        except Exception:
            pass
    if last_ts is not None:
        try:
            first_measure.insert(0, copy.deepcopy(last_ts))
        except Exception:
            pass

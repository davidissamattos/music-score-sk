# pylint: disable=too-many-branches
"""Utilities for transposing music scores with music21."""

from __future__ import annotations

from math import isclose
from pathlib import Path
from typing import BinaryIO

from music21 import interval as m21_interval
from music21 import key as m21_key
from music21 import stream as m21_stream

from .utils import infer_format_from_path, load_score, write_score


def transpose_score(
    *,
    source: str | None = None,
    output: str | None = None,
    steps: float,
    part_name: str | None = None,
    part_number: int | None = None,
    key_sharps: int | None = None,
    output_format: str | None = None,
    stdin_data: bytes | None = None,
    stdout_buffer: BinaryIO | None = None,
) -> str:
    """Transpose the score by the requested number of tones."""
    if part_name and part_number is not None:
        raise ValueError("Specify either part_name or part_number, not both.")

    semitones = _steps_to_semitones(steps)
    chromatic = m21_interval.ChromaticInterval(semitones)
    interval_obj = m21_interval.Interval(chromatic=chromatic)

    score = load_score(source, stdin_data=stdin_data)
    targets = _select_parts(score, part_name=part_name, part_number=part_number)

    for part in targets:
        part.transpose(interval_obj, inPlace=True)
        _apply_key_signature(part, key_sharps=key_sharps)

    target_format = _determine_format(
        output=output,
        explicit=output_format,
        fallback=infer_format_from_path(source, default="musicxml"),
    )
    message = write_score(
        score,
        target_format,
        output=output,
        stdout_buffer=stdout_buffer,
        write_kwargs={"makeNotation": False},
    )
    if output:
        source_name = Path(source).name if source else "stdin"
        return f"Created {Path(output)} by transposing {source_name} by {steps} tone(s)."
    return message


def _steps_to_semitones(steps: float) -> int:
    """Convert tone-based steps into semitone counts (0.5 tone == semitone)."""
    semitone_value = float(steps) * 2
    if not isclose(semitone_value, round(semitone_value), abs_tol=1e-9):
        raise ValueError("Steps must be provided in increments of 0.5.")
    return int(round(semitone_value))


def _select_parts(
    score: m21_stream.Score,
    *,
    part_name: str | None,
    part_number: int | None,
) -> list[m21_stream.Stream]:
    """Return parts that need transposition."""
    parts = list(score.parts)
    if not parts:
        return [score]

    if part_name:
        normalized = part_name.lower()
        matching = [
            part
            for part in parts
            if (part.partName or "").lower() == normalized
            or str(part.id or "").lower() == normalized
        ]
        if not matching:
            raise ValueError(f"No part named '{part_name}' found.")
        return matching

    if part_number is not None:
        if part_number < 1 or part_number > len(parts):
            raise ValueError(
                f"part_number must be between 1 and {len(parts)} (received {part_number})."
            )
        return [parts[part_number - 1]]

    return parts


def _apply_key_signature(
    target: m21_stream.Stream,
    *,
    key_sharps: int | None,
) -> None:
    """Adjust or replace the key signature for the target stream."""
    sharps_value: int | None
    if key_sharps is not None:
        sharps_value = int(key_sharps)
    else:
        try:
            analyzed_key = target.analyze("key")
            sharps_value = analyzed_key.sharps
        except Exception:  # pragma: no cover - fallback when analysis fails
            sharps_value = None

    if sharps_value is None:
        return

    new_signature = m21_key.KeySignature(sharps_value)

    for existing in list(target.recurse().getElementsByClass(m21_key.KeySignature)):
        site = existing.activeSite
        if site is not None:
            site.remove(existing)

    first_measure = next(iter(target.getElementsByClass(m21_stream.Measure)), None)
    container = first_measure if first_measure is not None else target
    container.insert(0, new_signature)


def _determine_format(
    *,
    output: str | None,
    explicit: str | None,
    fallback: str | None,
) -> str:
    """Pick the format for writing results."""
    if explicit:
        return explicit.strip().lower()
    if output:
        suffix = Path(output).suffix.lstrip(".")
        if suffix:
            return suffix.lower()
    if fallback:
        return fallback
    return "musicxml"

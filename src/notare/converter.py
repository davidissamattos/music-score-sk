"""Helpers that wrap music21 conversion utilities."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from music21 import converter as m21_converter

from .utils import load_score, write_score, _available_output_formats,list_output_formats





def convert_score(
    *,
    source: str | None = None,
    target_format: str,
    output: str | None = None,
    stdin_data: bytes | None = None,
    stdout_buffer: BinaryIO | None = None,
) -> str:
    """Convert source file to target_format and write it to output."""
    available_formats = _available_output_formats()
    normalized_format = target_format.strip().lower()
    if normalized_format not in available_formats:
        raise ValueError(
            f"Unsupported format '{target_format}'. Choose from: "
            f"{', '.join(available_formats)}"
        )

    score = load_score(source, stdin_data=stdin_data)
    message = write_score(
        score,
        target_format=normalized_format,
        output=output,
        stdout_buffer=stdout_buffer,
    )
    return message

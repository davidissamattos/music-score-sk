"""Helpers that wrap music21 conversion utilities."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from music21 import converter as m21_converter

from .utils import infer_format_from_path, load_score, write_score


def _available_output_formats() -> tuple[str, ...]:
    """Return sorted output formats supported by music21."""
    formats: set[str] = set()
    for sub_converter in m21_converter.Converter.subConvertersList("output"):
        base_formats = (
            fmt.lower()
            for fmt in getattr(sub_converter, "registerFormats", ())
            if fmt
        )
        subformats = getattr(sub_converter, "registerOutputSubformatExtensions", {}) or {}
        for base in base_formats:
            formats.add(base)
            for sub in subformats:
                formats.add(f"{base}.{sub.lower()}")
    return tuple(sorted(formats))


def list_output_formats() -> list[str]:
    """Expose the format list."""
    return list(_available_output_formats())


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
    return write_score(
        score,
        normalized_format,
        output=output,
        stdout_buffer=stdout_buffer,
    )

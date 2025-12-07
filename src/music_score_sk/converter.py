"""Helpers that wrap music21 conversion utilities."""

from __future__ import annotations
from pathlib import Path
from music21 import converter as m21_converter


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


def convert_score(*, source: str, target_format: str, output: str) -> str:
    """Convert source file to target_format and write it to output."""
    available_formats = _available_output_formats()
    normalized_format = target_format.strip().lower()
    if normalized_format not in available_formats:
        raise ValueError(
            f"Unsupported format '{target_format}'. Choose from: "
            f"{', '.join(available_formats)}"
        )

    source_path = Path(source).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    output_path = Path(output).expanduser()
    if output_path.parent and not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    base_format, *subformats = normalized_format.split(".")
    score = m21_converter.parse(str(source_path))
    written_path = score.write(base_format, fp=str(output_path), subformats=subformats)
    return f"Created {written_path} using format '{normalized_format}'."

"""Shared helpers for score IO operations."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
from typing import Any, BinaryIO

from music21 import converter as m21_converter
from music21 import stream as m21_stream


def load_score(source: str | None, *, stdin_data: bytes | None = None) -> m21_stream.Score:
    """Load a score from disk or stdin."""
    if source is None:
        raw = stdin_data if stdin_data is not None else sys.stdin.buffer.read()
        if not raw:
            raise ValueError("No input data received from stdin.")
        try:
            data = raw.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            data = raw
        return m21_converter.parseData(data)

    source_path = Path(source).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    return m21_converter.parse(str(source_path))


def write_score(
    score: m21_stream.Score,
    target_format: str,
    *,
    output: str | None,
    stdout_buffer: BinaryIO | None = None,
    write_kwargs: dict[str, Any] | None = None,
) -> str:
    """Write the score either to stdout or to a file path."""
    if output is None:
        buffer = stdout_buffer or sys.stdout.buffer
        _write_to_buffer(score, target_format, buffer, write_kwargs=write_kwargs)
        return f"Emitted {target_format} data to stdout."

    output_path = Path(output).expanduser()
    if output_path.parent and not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    score.write(target_format, fp=str(output_path), **(write_kwargs or {}))
    return f"Created {output_path} using format '{target_format}'."


def infer_format_from_path(path: str | None, *, default: str = "musicxml") -> str:
    """Guess a format from a file path, falling back to the provided default."""
    if path:
        suffix = Path(path).suffix.lstrip(".")
        if suffix:
            return suffix.lower()
    return default


def _write_to_buffer(
    score: m21_stream.Score,
    fmt: str,
    buffer: BinaryIO,
    *,
    write_kwargs: dict[str, Any] | None,
) -> None:
    suffix = f".{fmt.split('.')[0]}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        kwargs = write_kwargs or {}
        score.write(fmt, fp=str(tmp_path), **kwargs)
        with open(tmp_path, "rb") as handle:
            buffer.write(handle.read())
            buffer.flush()
    finally:
        tmp_path.unlink(missing_ok=True)

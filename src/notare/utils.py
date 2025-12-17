"""Shared helpers for score IO operations."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
from typing import Any, BinaryIO

from music21 import converter as m21_converter
from music21 import stream as m21_stream
from music21 import metadata as m21_metadata


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


def _available_input_formats() -> tuple[str, ...]:
    """Return sorted input formats supported by music21."""
    formats: set[str] = set()
    for sub_converter in m21_converter.Converter.subConvertersList("input"):
        base_formats = (
            fmt.lower()
            for fmt in getattr(sub_converter, "registerFormats", ())
            if fmt
        )
        for base in base_formats:
            formats.add(base)
    return tuple(sorted(formats))


def list_output_formats() -> list[str]:
    """Expose supported output formats."""
    return list(_available_output_formats())


def list_input_formats() -> list[str]:
    """Expose supported input formats."""
    return list(_available_input_formats())

def load_score(source: str | None, *, stdin_data: bytes | None = None) -> m21_stream.Score:
    """Load a score from disk or stdin and normalize empty fields.

    Ensures missing part names, title, and composer are empty strings.
    """
    # Treat '-' as stdin alias
    if source is None or (isinstance(source, str) and source.strip() == "-"):
        raw = stdin_data if stdin_data is not None else sys.stdin.buffer.read()
        if not raw:
            raise ValueError("No input data received from stdin.")
        try:
            data = raw.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            data = raw
        score = m21_converter.parseData(data)
    else:
        source_path = Path(source).expanduser()
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        score = m21_converter.parse(str(source_path))

    # Normalize metadata: ensure metadata exists and set empty strings when missing
    if score.metadata is None:
        score.insert(0, m21_metadata.Metadata())
    # Helper to detect placeholder/missing strings
    def _is_missing(value: object, placeholders: set[str]) -> bool:
        if value is None:
            return True
        if not isinstance(value, str):
            return False
        stripped = value.strip()
        if stripped == "":
            return True
        return stripped.lower() in placeholders

    title_placeholders = {"music21", "untitled", "title"}
    composer_placeholders = {"unknown", "composer", "music21"}

    if _is_missing(getattr(score.metadata, "title", None), title_placeholders):
        score.metadata.title = ""
    if _is_missing(getattr(score.metadata, "composer", None), composer_placeholders):
        score.metadata.composer = ""

    # Normalize part names
    try:
        part_placeholders = {"part", "musicxml part"}
        for idx, part in enumerate(score.parts):
            name = getattr(part, "partName", None)
            if _is_missing(name, part_placeholders):
                part.partName = f"Part {idx + 1}"
    except Exception:
        # In case score has no parts iterable, ignore
        pass

    # Renumber measures to always start at 1, regardless of pickup/anacrusis
    _renumber_measures_starting_at_one(score)

    return score

def _renumber_measures_starting_at_one(score: m21_stream.Score) -> None:
    """Ensure all measures in parts (or score if no parts) start at number 1.

    Some imports label pickup/anacrusis as measure 0 or None; normalize so
    subsequent operations can assume 1-based measure numbering consistently.
    """
    try:
        parts = list(score.parts)
    except Exception:
        parts = []

    targets: list[m21_stream.Stream]
    targets = parts if parts else [score]

    from music21 import stream as m21_stream_mod
    for target in targets:
        count = 0
        for meas in target.getElementsByClass(m21_stream_mod.Measure):
            count += 1
            try:
                meas.number = count
            except Exception:
                # If measure object doesn't allow setting, skip gracefully
                pass

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


def write_score(
    score: m21_stream.Score,
    target_format: str = 'musicxml',
    output: str | None = None,
    stdout_buffer: BinaryIO | None = None,
    write_kwargs: dict[str, Any] | None = None,
) -> str:
    """Write the score either to stdout or to a file path."""
    target_format = _determine_format(
        output=output,
        explicit=target_format,
        fallback="musicxml",
    )
    # Enable music21's notation processing to avoid inexpressible durations on export
    write_kwargs = {"makeNotation": True} if target_format in {"musicxml", "midi"} else None

    if output is None: 
        buffer = stdout_buffer or sys.stdout.buffer
        # If target_format is omitted or unsupported, fall back to musicxml for piping
        available = set(_available_output_formats())
        fmt = (target_format or "").strip().lower()
        if not fmt:
            effective_fmt = "musicxml"
        else:
            effective_fmt = fmt if fmt in available else "musicxml"
        _write_to_buffer(score, effective_fmt, buffer, write_kwargs=write_kwargs)
        return ""

    

    output_path = Path(output).expanduser()
    if output_path.parent and not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Validate format for file output
    available = set(_available_output_formats())
    fmt = target_format.strip().lower()
    if fmt not in available:
        raise ValueError(
            f"Unsupported output format '{target_format}'. Choose from: {', '.join(sorted(available))}"
        )
    score.write(fmt, fp=str(output_path), **(write_kwargs or {}))
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


# --- Shared selection helpers used by extract and delete ---

def _parse_measure_spec(spec: str | None) -> list[tuple[int, int]]:
    """Parse a comma-separated measure spec into list of (start, end) ranges.

    Accepts tokens like `1`, `3-5`, and removes accidental wrappers like parentheses/brackets.
    Normalizes each range to have start <= end.
    """
    if not spec:
        return []
    spec = spec.strip().strip("()[]")
    ranges: list[tuple[int, int]] = []
    for token in spec.split(","):
        token = token.strip().strip("()[]")
        if not token:
            continue
        if "-" in token:
            start_str, end_str = token.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
        else:
            start = end = int(token.strip())
        if start > end:
            start, end = end, start
        ranges.append((start, end))
    return ranges


def _parse_csv(value: str | None, *, lower: bool = False) -> list[str]:
    """Split a comma-separated string into normalized tokens."""
    if not value:
        return []
    tokens = [item.strip() for item in value.split(",") if item.strip()]
    if lower:
        tokens = [token.lower() for token in tokens]
    return tokens


def _select_parts(
    score: m21_stream.Score,
    *,
    part_names: str | None,
    part_numbers: str | None,
) -> list[m21_stream.Stream]:
    """Select parts by name/id or 1-based part numbers. Returns the matched parts.

    When a score has no explicit parts, returns a list containing the score stream itself.
    Raises ValueError if explicit selection doesn't match any available parts.
    """
    parts = list(score.parts)
    if not parts:
        return [score]

    name_set = set(_parse_csv(part_names, lower=True))
    number_set = set(int(value) for value in _parse_csv(part_numbers) if value.isdigit())

    if not name_set and not number_set:
        return parts

    selected: list[m21_stream.Stream] = []
    for idx, part in enumerate(parts, start=1):
        match = False
        if name_set:
            part_name = (getattr(part, "partName", "") or "").lower()
            part_id = (getattr(part, "id", "") or "").lower()
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
                [(getattr(p, "partName", None) or getattr(p, "id", None) or f"Part {i+1}") for i, p in enumerate(parts)],
            )
        )
        raise ValueError(f"No parts matched the selection. Available parts: {available}")
    return selected

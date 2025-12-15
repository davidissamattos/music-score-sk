"""Metadata inspection and editing utilities."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import BinaryIO

from music21 import metadata as m21_metadata
from music21 import stream as m21_stream

from .utils import infer_format_from_path, load_score, write_score

FIELD_LABELS = OrderedDict(
    [
        ("title", "Title"),
        ("author", "Author"),
        ("format", "Format"),
        ("composer", "Composer"),
        ("arranger", "Arranger"),
        ("number_parts", "Number of Parts"),
        ("number_measures", "Number of Measures"),
        ("key_signature", "Key Signature"),
        ("tempo", "Tempo"),
    ]
)


def metadata_summary(
    *,
    source: str | None = None,
    output: str | None = None,
    output_format: str | None = None,
    stdin_data: bytes | None = None,
    stdout_buffer: BinaryIO | None = None,
    fields: list[str] | None = None,
    updates: dict[str, str | None] | None = None,
) -> str:
    """Generate a metadata summary and optionally update fields."""
    score = load_score(source, stdin_data=stdin_data)
    info = _extract_metadata(score, source_path=source)

    requested_fields = fields or list(FIELD_LABELS.keys())
    lines = []
    for field in requested_fields:
        label = FIELD_LABELS.get(field, field.title())
        value = info.get(field, "N/A")
        lines.append(f"{label}: {value}")
    summary = "\n".join(lines)

    update_payload = {k: v for k, v in (updates or {}).items() if v is not None}
    if not update_payload:
        return summary

    _apply_metadata_updates(score, update_payload)
    base_default = infer_format_from_path(source, default="musicxml")
    target_format = output_format or infer_format_from_path(output, default=base_default)
    write_message = write_score(
        score,
        target_format,
        output=output,
        stdout_buffer=stdout_buffer,
    )
    return f"{summary}\n{write_message}"


def _extract_metadata(score: m21_stream.Score, source_path: str | None) -> dict[str, str]:
    info: dict[str, str] = {}
    meta = score.metadata or m21_metadata.Metadata()

    info["title"] = _safe_meta_attr(meta, "title") or _get_custom_value(meta, "Title") or "Unknown"
    info["author"] = _get_custom_value(meta, "Author") or "Unknown"
    info["format"] = meta.fileFormat or infer_format_from_path(source_path, default="musicxml")
    info["composer"] = _safe_meta_attr(meta, "composer") or "Unknown"
    info["arranger"] = _safe_meta_attr(meta, "arranger") or "Unknown"

    parts = list(score.parts)
    info["number_parts"] = str(len(parts) if parts else 0)
    info["number_measures"] = (
        _get_custom_value(meta, "Number Of Measures")
        or str(_estimate_measure_count(score, parts))
    )
    info["number_parts"] = _get_custom_value(meta, "Number Of Parts") or info["number_parts"]
    info["key_signature"] = _get_custom_value(meta, "Key Signature") or _detect_key_signature(score)
    info["tempo"] = _get_custom_value(meta, "Tempo") or _detect_tempo(score)
    return info


def _estimate_measure_count(score: m21_stream.Score, parts: list[m21_stream.Stream]) -> int:
    if parts:
        return max(
            (
                len(list(part.getElementsByClass(m21_stream.Measure)))
                for part in parts
            ),
            default=0,
        )
    return len(list(score.getElementsByClass(m21_stream.Measure)))


def _detect_key_signature(score: m21_stream.Score) -> str:
    try:
        key = score.analyze("key")
        return key.name
    except Exception:  # pragma: no cover - analysis can fail
        return "Unknown"


def _detect_tempo(score: m21_stream.Score) -> str:
    try:
        boundaries = score.metronomeMarkBoundaries()
        if boundaries:
            mark = boundaries[0][2]
            if mark.number:
                return f"{int(mark.number)} BPM"
            if mark.text:
                return mark.text
    except Exception:  # pragma: no cover - tempo detection best effort
        pass
    return "Unknown"


def _apply_metadata_updates(score: m21_stream.Score, updates: dict[str, str]) -> None:
    if not updates:
        return
    if score.metadata is None:
        score.metadata = m21_metadata.Metadata()
    meta = score.metadata

    for field, value in updates.items():
        text_value = str(value)
        if field in {"title", "author", "composer", "arranger"}:
            if field == "author":
                _set_custom_value(meta, FIELD_LABELS[field], text_value)
            else:
                setattr(meta, field, text_value)
        elif field == "format":
            meta.fileFormat = text_value
        else:
            label = FIELD_LABELS.get(field, field.replace("_", " ").title())
            _set_custom_value(meta, label, text_value)


def _safe_meta_attr(meta: m21_metadata.Metadata, attribute: str) -> str | None:
    try:
        return getattr(meta, attribute)
    except AttributeError:
        return None


def _get_custom_value(meta: m21_metadata.Metadata, label: str) -> str | None:
    try:
        entries = list(meta.all())
    except Exception:
        return None
    for entry in reversed(entries):
        name = getattr(entry, "name", None)
        value = getattr(entry, "value", None)
        if name is None and isinstance(entry, tuple) and len(entry) >= 2:
            name, value = entry[0], entry[1]
        if name and name.lower() == label.lower():
            return "" if value is None else str(value)
    return None


def _set_custom_value(meta: m21_metadata.Metadata, label: str, value: str) -> None:
    meta.add(label, value)

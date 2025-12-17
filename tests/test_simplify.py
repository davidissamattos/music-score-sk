"""Tests for simplify module and ornament removal algorithm."""

from __future__ import annotations

from pathlib import Path
import io

from music21 import converter as m21_converter
from music21 import duration as m21_duration
from music21 import meter as m21_meter
from music21 import note as m21_note
from music21 import stream as m21_stream

from notare.simplify import simplify_score


def _make_score_with_notes(notes: list[m21_note.Note]) -> m21_stream.Score:
    score = m21_stream.Score()
    part = m21_stream.Part()
    meas = m21_stream.Measure(number=1)
    meas.insert(0, m21_meter.TimeSignature("4/4"))
    for n in notes:
        meas.append(n)
    part.append(meas)
    score.insert(0, part)
    return score


def _musicxml_bytes(score: m21_stream.Score) -> bytes:
    tmp = Path.cwd() / "_tmp_test_simplify.musicxml"
    try:
        score.write("musicxml", fp=str(tmp))
        return tmp.read_bytes()
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def test_ornament_removal_grace_neighbor_removed() -> None:
    # C8th, grace D, Cquarter — grace should be removed
    n1 = m21_note.Note("C4")
    n1.duration = m21_duration.Duration(0.5)

    n2 = m21_note.Note("D4")
    n2.makeGrace()

    n3 = m21_note.Note("C4")
    n3.duration = m21_duration.Duration(1.0)

    score = _make_score_with_notes([n1, n2, n3])
    source_bytes = _musicxml_bytes(score)

    buffer = io.BytesIO()
    simplify_score(
        algorithms=[("ornament_removal", {"duration": "1/8"})],
        stdin_data=source_bytes,
        stdout_buffer=buffer,
    )

    out = m21_converter.parseData(buffer.getvalue())
    part = out.parts[0] if out.parts else out
    names = [n.pitch.nameWithOctave for n in part.recurse().notes]
    assert names == ["C4", "C4"]


def test_ornament_removal_duration_parameter_controls_threshold(tmp_path: Path) -> None:
    # C8th, D16th, Cquarter — remove only when threshold >= 1/8 beat
    n1 = m21_note.Note("C4")
    n1.duration = m21_duration.Duration(0.5)

    n2 = m21_note.Note("D4")
    n2.duration = m21_duration.Duration(0.125)  # Sixteenth relative to quarter beat

    n3 = m21_note.Note("C4")
    n3.duration = m21_duration.Duration(1.0)

    score = _make_score_with_notes([n1, n2, n3])

    # Write input once
    in_path = tmp_path / "in.musicxml"
    score.write("musicxml", fp=str(in_path))

    # With 1/16 threshold (0.0625 of beat), D16th is NOT removed
    out1 = tmp_path / "out1.musicxml"
    simplify_score(
        algorithms=[("ornament_removal", {"duration": "1/16"})],
        source=str(in_path),
        output=str(out1),
    )
    out_score1 = m21_converter.parse(str(out1))
    part1 = out_score1.parts[0] if out_score1.parts else out_score1
    names1 = [n.pitch.nameWithOctave for n in part1.recurse().notes]
    assert names1 == ["C4", "D4", "C4"]

    # With 1/4 threshold (0.25 of beat), D16th IS removed
    out2 = tmp_path / "out2.musicxml"
    simplify_score(
        algorithms=[("ornament_removal", {"duration": "1/4"})],
        source=str(in_path),
        output=str(out2),
    )

    out_score2 = m21_converter.parse(str(out2))
    part2 = out_score2.parts[0] if out_score2.parts else out_score2
    names2 = [n.pitch.nameWithOctave for n in part2.recurse().notes]
    assert names2 == ["C4", "C4"]


def test_simplify_supports_piping() -> None:
    # Create a score with a remove-worthy ornament and use stdin/stdout
    n1 = m21_note.Note("C4")
    n1.duration = m21_duration.Duration(0.5)
    n2 = m21_note.Note("D4")
    n2.duration = m21_duration.Duration(0.125)
    n3 = m21_note.Note("C4")
    n3.duration = m21_duration.Duration(1.0)
    score = _make_score_with_notes([n1, n2, n3])
    source_bytes = _musicxml_bytes(score)

    buffer = io.BytesIO()
    simplify_score(
        algorithms=[("ornament_removal", {"duration": "1/4"})],
        stdin_data=source_bytes,
        stdout_buffer=buffer,
    )

    out = m21_converter.parseData(buffer.getvalue())
    part = out.parts[0] if out.parts else out
    names = [n.pitch.nameWithOctave for n in part.recurse().notes]
    assert names == ["C4", "C4"]

"""Tests for the delete module."""

from __future__ import annotations

from pathlib import Path

from music21 import converter as m21_converter
from music21 import note
from music21 import stream
from notare.utils import load_score

from notare.delete import delete_sections


def _build_score(tmp_path: Path) -> Path:
    score = stream.Score()
    for idx, part_name in enumerate(["Flute", "Oboe"], start=1):
        part = stream.Part(id=f"P{idx}")
        part.partName = part_name
        for measure_number in range(1, 6):
            measure = stream.Measure(number=measure_number)
            pitch_name = chr(ord("C") + measure_number - 1)
            measure.append(note.Note(pitch_name + "4"))
            part.append(measure)
        score.insert(idx - 1, part)
    source = tmp_path / "source.musicxml"
    score.write("musicxml", fp=str(source))
    return source


def test_delete_measures(tmp_path):
    source = _build_score(tmp_path)
    output = tmp_path / "delete_measures.musicxml"

    delete_sections(
        source=str(source),
        output=str(output),
        measures="2-3",
    )

    new_score = m21_converter.parse(str(output))
    first_part = new_score.parts[0]
    measures = list(first_part.getElementsByClass(stream.Measure))
    assert len(measures) == 3  # kept: 1,4,5 -> renumbered to 1,2,3
    assert [m.number for m in measures] == [1, 2, 3]


def test_delete_specific_part_by_name(tmp_path):
    source = _build_score(tmp_path)
    output = tmp_path / "delete_part_name.musicxml"

    delete_sections(
        source=str(source),
        output=str(output),
        part_names="Oboe",
    )

    new_score = m21_converter.parse(str(output))
    assert len(new_score.parts) == 1
    assert new_score.parts[0].partName == "Flute"


def test_delete_combined_measures_and_part_numbers(tmp_path):
    source = _build_score(tmp_path)
    output = tmp_path / "delete_combined.musicxml"

    delete_sections(
        source=str(source),
        output=str(output),
        part_numbers="2",
        measures="1",
    )

    new_score = m21_converter.parse(str(output))
    # Only part 1 remains
    assert len(new_score.parts) == 1
    assert new_score.parts[0].partName == "Flute"
    measures = list(new_score.parts[0].getElementsByClass(stream.Measure))
    # Original measures 2..5 kept -> renumbered to 1..4
    assert len(measures) == 4
    assert [m.number for m in measures] == [1, 2, 3, 4]


# --- Tests using the real MusicXML examples in tests/data ---

def _musicxml_samples() -> list[Path]:
    data_dir = Path(__file__).parent / "data"
    return sorted(data_dir.glob("*.musicxml"))


def _first_stream_with_measures(score: stream.Score) -> stream.Stream:
    parts = list(getattr(score, "parts", []))
    return parts[0] if parts else score


def test_delete_first_measure_on_samples(tmp_path):
    for sample in _musicxml_samples():
        # Use load_score to normalize measure numbering before counting
        original = load_score(str(sample))
        source_count = len(list(_first_stream_with_measures(original).getElementsByClass(stream.Measure)))

        output = tmp_path / f"{sample.stem}_del1.musicxml"
        delete_sections(
            source=str(sample),
            output=str(output),
            measures="1",
        )

        new_score = m21_converter.parse(str(output))
        first_stream = _first_stream_with_measures(new_score)
        measures = list(first_stream.getElementsByClass(stream.Measure))
        # New behavior: when all measures would be removed, keep a single empty measure
        assert len(measures) == max(source_count - 1, 1)
        assert [m.number for m in measures] == list(range(1, len(measures) + 1))


def test_delete_two_measures_on_samples(tmp_path):
    for sample in _musicxml_samples():
        original = load_score(str(sample))
        source_count = len(list(_first_stream_with_measures(original).getElementsByClass(stream.Measure)))

        output = tmp_path / f"{sample.stem}_del1_2.musicxml"
        delete_sections(
            source=str(sample),
            output=str(output),
            measures="1-2",
        )

        new_score = m21_converter.parse(str(output))
        first_stream = _first_stream_with_measures(new_score)
        measures = list(first_stream.getElementsByClass(stream.Measure))
        # New behavior: when all measures would be removed, keep a single empty measure
        expected = max(source_count - 2, 1)
        assert len(measures) == expected
        assert [m.number for m in measures] == list(range(1, len(measures) + 1))

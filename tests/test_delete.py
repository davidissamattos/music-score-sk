"""Tests for the delete module."""

from __future__ import annotations

from pathlib import Path

from music21 import converter as m21_converter
from music21 import note
from music21 import stream
from notare.utils import load_score

from notare.delete import delete_sections, delete_lyrics, delete_chords, delete_fingering, delete_annotations
from music21 import harmony as m21_harmony
from music21 import expressions as m21_expr
from music21 import articulations as m21_art


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


def test_delete_lyrics_from_sample_sozinho(tmp_path):
    sample = Path(__file__).parent / "data" / "sozinho.musicxml"
    output = tmp_path / "sozinho_nolyrics.musicxml"

    delete_lyrics(source=str(sample), output=str(output))

    score = m21_converter.parse(str(output))
    for n in score.recurse().notes:
        if hasattr(n, "lyric"):
            assert getattr(n, "lyric") in (None, "",)
        lyr_list = list(getattr(n, "lyrics", []) or [])
        assert len(lyr_list) == 0


def test_delete_chords_from_sample_sozinho(tmp_path):
    sample = Path(__file__).parent / "data" / "sozinho.musicxml"
    output = tmp_path / "sozinho_nochords.musicxml"

    delete_chords(source=str(sample), output=str(output))

    score = m21_converter.parse(str(output))
    chord_syms = list(score.recurse().getElementsByClass((m21_harmony.ChordSymbol, m21_harmony.Harmony)))
    assert len(chord_syms) == 0


def test_delete_fingering_scoped_by_measures(tmp_path):
    # Build a tiny score with fingerings in two measures
    s = stream.Score()
    p = stream.Part(id="P1")
    p.partName = "Test"
    for i in range(1, 3):
        m = stream.Measure(number=i)
        n = note.Note("C4")
        n.articulations = [m21_art.Fingering(1)]
        m.append(n)
        p.append(m)
    s.insert(0, p)
    source = tmp_path / "fing.musicxml"
    out = tmp_path / "fing_out.musicxml"
    s.write("musicxml", fp=str(source))

    delete_fingering(source=str(source), output=str(out), measures="1")

    sc = m21_converter.parse(str(out))
    ms = list(sc.parts[0].getElementsByClass(stream.Measure))
    arts_m1 = list(ms[0].notes[0].articulations)
    arts_m2 = list(ms[1].notes[0].articulations)
    assert all(not isinstance(a, m21_art.Fingering) for a in arts_m1)
    assert any(isinstance(a, m21_art.Fingering) for a in arts_m2)


def test_delete_annotations_on_note(tmp_path):
    s = stream.Score()
    p = stream.Part(id="P1")
    p.partName = "Test"
    m = stream.Measure(number=1)
    n = note.Note("C4")
    n.expressions = [m21_expr.TextExpression("hello"), m21_expr.RehearsalMark("A")]
    m.append(n)
    p.append(m)
    s.insert(0, p)
    source = tmp_path / "ann.musicxml"
    out = tmp_path / "ann_out.musicxml"
    s.write("musicxml", fp=str(source))

    delete_annotations(source=str(source), output=str(out))

    sc = m21_converter.parse(str(out))
    exprs = list(sc.recurse().getElementsByClass((m21_expr.TextExpression, m21_expr.RehearsalMark)))
    assert len(exprs) == 0

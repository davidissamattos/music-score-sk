"""Command line interface for the notare package."""

from __future__ import annotations

from collections.abc import Sequence
import sys

import fire

from . import __version__
from .converter import convert_score
from .metadata import metadata_summary
from .metadata import set_metadata as set_metadata_cmd
from .metadata import set_part_metadata as set_part_metadata_cmd
from .extract import extract_sections
from .delete import delete_sections, delete_lyrics as delete_lyrics_cmd, delete_annotations as delete_annotations_cmd, delete_fingering as delete_fingering_cmd, delete_chords as delete_chords_cmd
from .transpose import transpose_score
from .analyze import analyze_score
from .show import show_score
from .play import play_score
from .simplify import simplify_score
from .insert import add_sections
from .utils import  list_output_formats, list_input_formats


class ScoreTool:
    """notare — a command line utility tool for music score manipulation. Supports piping for easy multi-step workflows and integrations with other system tools.

    General usage
    - Print version: `notare version`
    - List supported formats: `notare formats`
    - Read from files with `--source` or from stdin by piping (omit `--source`).
    - Write to a file with `--output`. When omitted on converting, data may be streamed to stdout.

    Modules
    - formats: List supported input and output formats
    - version: Print the notare package version
    - convert: Convert between formats (e.g., MusicXML ↔ MIDI, PDF via LilyPond/MuseScore)
    - transpose: Transpose scores (per part or whole) and adjust key signatures
    - metadata: Show detailed metadata or print single requested fields; can also update fields
    - set-metadata: Set a single general metadata field and write the result
    - extract: Slice measures and/or select parts; write excerpt
    - analyze: Compute analysis metrics (key clarity, entropy, densities, etc.)
    - show: Render in browser via OSMD; optional `--print` to open the print dialog
    - play: Render to MIDI and open the default system player (no stdout)

    Tips
    - Windows uses `type` for piping (`type file.musicxml | notare ...`).
    - macOS/Linux uses `cat` for piping (`cat file.musicxml | notare ...`).
    """

    def version(self) -> str:
        """Return the package version."""
        return __version__

    def formats(self) -> list[str]:
        """List supported input and output formats reported by music21.

        Prints two lists:
        - Output formats (including subformats like `musicxml.pdf` if configured)
        - Input formats that can be parsed
        """
        print("Supported output formats:")
        for fmt in list_output_formats():
            print(f" - {fmt}")
        print("Supported input formats:")
        for fmt in list_input_formats():
            print(f" - {fmt}")

    def convert(
        self,
        *,
        source: str | None = None,
        format: str,
        output: str | None = None,
    ) -> str:
        """Convert a score to the requested format.

        Args
        - source: Path to input file. Omit to read from stdin (pipe).
        - format: Target format, e.g., `musicxml`, `midi`, `musicxml.pdf`.
        - output: Path to write the result. If omitted, data is streamed to stdout when supported.

        Examples
        - `notare convert --source score.musicxml --format midi --output score.mid`
        - `type score.abc | notare convert --format musicxml > out.musicxml` (Windows)
        - `cat score.musicxml | notare convert --format musicxml.pdf > out.pdf` (requires LilyPond/MuseScore)
        """
        return convert_score(source=source, target_format=format, output=output)

    def transpose(
        self,
        interval: float,
        *,
        source: str | None = None,
        output: str | None = None,
        part_name: str | None = None,
        part_number: int | None = None,
        key_sharps: int | None = None,
        output_format: str | None = None,
    ) -> str:
        """Transpose the input score by the provided number of tones.

        Args
        - interval: Tones (use 0.5 for semitones; negative to transpose down)
        - part_name / part_number: Limit transposition to a single part
        - key_sharps: Force resulting key signature (accidentals count)
        - output_format: Explicit output format (e.g., `musicxml`, `midi`)

        Examples
        - `notare transpose 1 --source score.musicxml --output up.musicxml`
        - `notare transpose -0.5 --source score.musicxml --part-number 1 --output part1_down.musicxml`
        """
        return transpose_score(
            source=source,
            output=output,
            steps=interval,
            part_name=part_name,
            part_number=part_number,
            key_sharps=key_sharps,
            output_format=output_format,
        )

    def metadata(
        self,
        *,
        source: str | None = None,
        output: str | None = None,
        output_format: str | None = None,
        title: bool = False,
        subtitle: bool = False,
        author: bool = False,
        format: bool = False,
        rights: bool = False,
        software: bool = False,
        composer: bool = False,
        arranger: bool = False,
        number_parts: bool = False,
        number_measures: bool = False,
        key_signature: bool = False,
        musical_key: bool = False,
        tempo: bool = False,
        time_signature: bool = False,
        clef: bool = False,
        new_title: str | None = None,
        new_author: str | None = None,
        new_format: str | None = None,
        new_composer: str | None = None,
        new_arranger: str | None = None,
        new_number_parts: str | None = None,
        new_number_measures: str | None = None,
        new_key_signature: str | None = None,
        new_tempo: str | None = None,
    ) -> str:
        """Inspect and optionally update score metadata.

        Behavior
        - No field flags: prints a detailed summary (title/subtitle/composer/arranger,
            rights/software, measure/part counts, per-part clefs/key-signatures/musical-key/tempos).
        - One field flag: prints only the value (no label); ideal for scripting.
        - Multiple field flags: prints selected fields as `Label: value` lines; part-related
            fields (`--key-signature`, `--musical-key`, `--clef`) print per-part sections.

        Common fields
        - General: `--title`, `--subtitle`, `--author`, `--format`, `--rights`, `--software`,
            `--composer`, `--arranger`, `--number-parts`, `--number-measures`, `--time-signature`, `--tempo`
        - Per-part: `--key-signature`, `--musical-key`, `--clef`

        Updates
        - Use `--new-title`, `--new-author`, etc., with `--output` to write changes.

        Examples
        - `notare metadata --source score.musicxml`
        - `notare metadata --source score.musicxml --title`
        - `type score.musicxml | notare metadata --composer --key-signature --clef`
        - `notare metadata --source score.musicxml --new-title "My Title" --output updated.musicxml`
        """
        fields = [
            field
            for field, enabled in [
                ("title", title),
                ("subtitle", subtitle),
                ("author", author),
                ("format", format),
                ("rights", rights),
                ("software", software),
                ("composer", composer),
                ("arranger", arranger),
                ("number_parts", number_parts),
                ("number_measures", number_measures),
                ("key_signature", key_signature),
                ("musical_key", musical_key),
                ("tempo", tempo),
                ("time_signature", time_signature),
                ("clef", clef),
            ]
            if enabled
        ]
        updates = {
            "title": new_title,
            "author": new_author,
            "format": new_format,
            "composer": new_composer,
            "arranger": new_arranger,
            "number_parts": new_number_parts,
            "number_measures": new_number_measures,
            "key_signature": new_key_signature,
            "tempo": new_tempo,
        }
        return metadata_summary(
            source=source,
            output=output,
            output_format=output_format,
            fields=fields or None,
            updates=updates,
        )

    def extract(
        self,
        *,
        source: str | None = None,
        output: str | None = None,
        output_format: str | None = None,
        measures: str | None = None,
        part_name: str | None = None,
        part_number: str | None = None,
    ) -> str:
        """Extract specific measures and/or parts from a score.

        Args
        - measures: Comma-separated indices and ranges, e.g., `1,3,5-8`. Measure numbering is normalized
            to start at 1 on import; `0` is treated as 1.
        - part-name: Comma-separated part names/ids
        - part-number: Comma-separated part numbers (1-based)

        Examples
        - `notare extract --source score.musicxml --measures 1-4 --part-name Flute,Oboe --output excerpt.musicxml`
        - `type score.musicxml | notare extract --measures 1,3 | notare show`
        """
        return extract_sections(
            source=source,
            output=output,
            output_format=output_format,
            measures=measures,
            part_names=part_name,
            part_numbers=part_number,
        )

    def delete(
        self,
        *,
        source: str | None = None,
        output: str | None = None,
        output_format: str | None = None,
        measures: str | None = None,
        part_name: str | None = None,
        part_number: str | None = None,
    ) -> str:
        """Delete specific measures and/or parts from a score.

        Args
        - measures: Comma-separated indices and ranges to delete, e.g., `1,3,5-8`. Measure numbering
            is normalized to start at 1 on import; pickup/anacrusis is treated as 1.
        - part-name: Comma-separated part names/ids to delete
        - part-number: Comma-separated part numbers (1-based) to delete

        Behavior
        - Metadata is preserved. After deletions, measures are renumbered to start at 1.

        Examples
        - `notare delete --source score.musicxml --measures 2-3 --output pruned.musicxml`
        - `notare delete --source score.musicxml --part-name Oboe --output no_oboe.musicxml`
        - `type score.musicxml | notare delete --measures 1,3 | notare show`
        """
        return delete_sections(
            source=source,
            output=output,
            output_format=output_format,
            measures=measures,
            part_names=part_name,
            part_numbers=part_number,
        )

    def delete_lyrics(
        self,
        *,
        source: str | None = None,
        output: str | None = None,
        output_format: str | None = None,
        measures: str | None = None,
        part_name: str | None = None,
        part_number: str | None = None,
    ) -> str:
        """Delete lyrics from the score. Scope with --measures/--part-name/--part-number or omit to delete all."""
        return delete_lyrics_cmd(
            source=source,
            output=output,
            output_format=output_format,
            measures=measures,
            part_names=part_name,
            part_numbers=part_number,
        )

    def delete_annotations(
        self,
        *,
        source: str | None = None,
        output: str | None = None,
        output_format: str | None = None,
        measures: str | None = None,
        part_name: str | None = None,
        part_number: str | None = None,
    ) -> str:
        """Delete text annotations (expressions) from the score. Scope with --measures/--part-name/--part-number or omit to delete all."""
        return delete_annotations_cmd(
            source=source,
            output=output,
            output_format=output_format,
            measures=measures,
            part_names=part_name,
            part_numbers=part_number,
        )

    def delete_fingering(
        self,
        *,
        source: str | None = None,
        output: str | None = None,
        output_format: str | None = None,
        measures: str | None = None,
        part_name: str | None = None,
        part_number: str | None = None,
    ) -> str:
        """Delete fingering marks. Scope with --measures/--part-name/--part-number or omit to delete all."""
        return delete_fingering_cmd(
            source=source,
            output=output,
            output_format=output_format,
            measures=measures,
            part_names=part_name,
            part_numbers=part_number,
        )

    def delete_chords(
        self,
        *,
        source: str | None = None,
        output: str | None = None,
        output_format: str | None = None,
        measures: str | None = None,
        part_name: str | None = None,
        part_number: str | None = None,
    ) -> str:
        """Delete chord symbols (harmony). Scope with --measures/--part-name/--part-number or omit to delete all."""
        return delete_chords_cmd(
            source=source,
            output=output,
            output_format=output_format,
            measures=measures,
            part_names=part_name,
            part_numbers=part_number,
        )

    def analyze(
        self,
        *,
        source: str | None = None,
        title: bool = False,
        key: bool = False,
        key_clarity: bool = False,
        interval_entropy: bool = False,
        pitch_class_entropy: bool = False,
        npvi: bool = False,
        contour_complexity: bool = False,
        highest_note: bool = False,
        rhythmic_variety: bool = False,
        avg_duration: bool = False,
        number_of_notes: bool = False,
        key_signature: bool = False,
        time_signature: bool = False,
        pitch_range: bool = False,
        articulation_density: bool = False,
        note_density: bool = False,
        avg_tempo: bool = False,
        dynamic_range: bool = False,
        difficulty: bool = False,
        difficulty_categories: bool = False,
    ) -> str:
        """Analyze a score and report requested metrics.

        Metrics (combine flags):
        - title, key, key_clarity, interval_entropy, pitch_class_entropy, npvi,
            contour_complexity, highest_note, rhythmic_variety, avg_duration,
            number_of_notes, key_signature, time_signature, pitch_range,
            articulation_density, note_density, avg_tempo, dynamic_range,
            difficulty, difficulty_categories

        Examples
        - `notare analyze --source score.musicxml --key --npvi`
        - `notare extract --source score.musicxml --measures 1-4 --output - | notare analyze --key`
        """
        metrics = [
            name
            for name, enabled in [
                ("title", title),
                ("key", key),
                ("key_clarity", key_clarity),
                ("interval_entropy", interval_entropy),
                ("pitch_class_entropy", pitch_class_entropy),
                ("npvi", npvi),
                ("contour_complexity", contour_complexity),
                ("highest_note", highest_note),
                ("rhythmic_variety", rhythmic_variety),
                ("avg_duration", avg_duration),
                ("number_of_notes", number_of_notes),
                ("key_signature", key_signature),
                ("time_signature", time_signature),
                ("pitch_range", pitch_range),
                ("articulation_density", articulation_density),
                ("note_density", note_density),
                ("avg_tempo", avg_tempo),
                ("dynamic_range", dynamic_range),
                ("difficulty", difficulty),
                ("difficulty_categories", difficulty_categories),
            ]
            if enabled
        ]
        return analyze_score(source=source, metrics=metrics or None)

    def set_metadata(
        self,
        *,
        source: str | None = None,
        output: str | None = None,
        title: str | None = None,
        subtitle: str | None = None,
        author: str | None = None,
        format: str | None = None,
        rights: str | None = None,
        composer: str | None = None,
        arranger: str | None = None,
    ) -> str:
        """Set a single general metadata attribute and write the score.

        Use exactly one of: --title, --subtitle, --author, --format, --rights, --composer, --arranger.

        Writes to --output if provided, otherwise streams to stdout (supports piping).
        """
        return set_metadata_cmd(
            source=source,
            output=output,
            title=title,
            subtitle=subtitle,
            author=author,
            format=format,
            rights=rights,
            composer=composer,
            arranger=arranger,
        )

    def set_part_metadata(
        self,
        *,
        source: str | None = None,
        output: str | None = None,
        part_name: str | None = None,
        part_number: int | None = None,
        name: str | None = None,
        order: int | None = None,
    ) -> str:
        """Set part-specific metadata: rename a part and/or change its order.

        Examples
        - `notare set-part-metadata --source score.musicxml --part-name "Part 1" --name "New part name" --output out.musicxml`
        - `notare set-part-metadata --source score.musicxml --part-number 2 --order 1 --output out.musicxml`
        """
        return set_part_metadata_cmd(
            source=source,
            output=output,
            part_name=part_name,
            part_number=part_number,
            name=name,
            order=order,
        )

    def show(
        self,
        *,
        source: str | None = None,
        hide_title: bool = False,
        hide_author: bool = False,
        hide_composer: bool = False,
        hide_part_names: bool = False,
        print: bool = False,
    ) -> str:
        """Render the score in a browser using OSMD.

        Args
        - source: Path to input file; omit to read from stdin (pipe)
        - hide-* flags: Hide title/author/composer/part names
        - print: Auto-open the browser print dialog after rendering

        Examples
        - `notare show --source score.musicxml`
        - `cat score.musicxml | notare show --hide-author` (macOS/Linux)
        - `type score.musicxml | notare show --print` (Windows)
        """
        return show_score(
            source=source,
            hide_title=hide_title,
            hide_author=hide_author,
            hide_composer=hide_composer,
            hide_part_names=hide_part_names,
            auto_print=print,
        )

    def play(
        self,
        *,
        source: str | None = None,
    ) -> str:
        """Play the score by rendering to MIDI and opening the default player.

        Behavior
        - Renders a temporary `.mid` file via music21 and opens it using the OS default app.
        - Does not write to stdout; suitable for interactive use.

        Examples
        - `notare play --source score.musicxml`
        - `cat score.musicxml | notare play` (macOS/Linux)
        - `type score.musicxml | notare play` (Windows)
        """
        return play_score(
            source=source,
        )

    def simplify(
        self,
        *,
        source: str | None = None,
        output: str | None = None,
        output_format: str | None = None,
        measures: str | None = None,
        part_name: str | None = None,
        part_number: str | None = None,
        ornament_removal: bool = False,
        ornament_removal_duration: str | None = None,
    ) -> str:
        """Simplify a score by applying selected algorithms in appearance order.

        --part-name and --part-number can be used to scope the simplification to specific parts.
        --measures can be used to scope the simplification to specific measures.

        Algorithms
        - `--ornament-removal`: Enable removal of grace notes, turns/trills components,
          and very short-duration neighbors using a heuristic. Optional parameter:
          `--ornament-removal-duration` (e.g., "1/8") controls the maximum ornament
          length as a fraction of the local beat.

        IO
        - Omit `--source` to read from stdin (pipe). Omit `--output` to stream to stdout.

        Examples
        - `notare simplify --source score.musicxml --ornament-removal --output simplified.musicxml`
        - `type score.musicxml | notare simplify --ornament-removal --ornament-removal-duration "1/8"`
        """
        # Build ordered algorithm list (future: derive exact order from argv tokens)
        algorithms: list[tuple[str, dict[str, str]]] = []
        if ornament_removal:
            params = {}
            if ornament_removal_duration:
                params["duration"] = ornament_removal_duration
            algorithms.append(("ornament_removal", params))

        return simplify_score(
            source=source,
            output=output,
            output_format=output_format,
            measures=measures,
            part_names=part_name,
            part_numbers=part_number,
            algorithms=algorithms,
        )

    def insert(
        self,
        *,
        original: str,
        to_add: str,
        measure: int,
        before: bool = True,
        output: str | None = None,
        output_format: str | None = None,
    ) -> str:
        """Insert measures and parts from one score into another.

        Examples
        - `notare insert --original a.musicxml --to-add b.musicxml --measure 1 --before --output out.musicxml`

        Behavior
        - Parts matched by name receive the inserted measures from `to_add`.
        - Other original parts receive rest measures for alignment.
        - Unmatched `to_add` parts are created as new parts and aligned with rests as needed.
        """
        return add_sections(
            original=original,
            to_add=to_add,
            measure=measure,
            before=before,
            output=output,
            output_format=output_format,
        )


def main(argv: Sequence[str] | None = None) -> None:
    """Entrypoint used by the console script."""
    command = list(argv) if argv is not None else sys.argv[1:]
    fire.Fire(ScoreTool, command=command)


if __name__ == "__main__":
    main()

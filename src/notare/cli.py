"""Command line interface for the notare package."""

from __future__ import annotations

from collections.abc import Sequence
import sys

import fire

from . import __version__
from .converter import convert_score, list_output_formats
from .metadata import metadata_summary
from .extract import extract_sections
from .transpose import transpose_score
from .analyze import analyze_score


class ScoreTool:
    """Swiss-knife commands for manipulating score files."""

    def version(self) -> str:
        """Return the package version."""
        return __version__

    def formats(self) -> list[str]:
        """List supported output formats."""
        return list_output_formats()

    def convert(
        self,
        *,
        source: str | None = None,
        format: str,
        output: str | None = None,
    ) -> str:
        """Convert a score to the requested format."""
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
        """Transpose the input score by the provided number of tones."""
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
        author: bool = False,
        format: bool = False,
        composer: bool = False,
        arranger: bool = False,
        number_parts: bool = False,
        number_measures: bool = False,
        key_signature: bool = False,
        tempo: bool = False,
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
        """Inspect and optionally update score metadata."""
        fields = [
            field
            for field, enabled in [
                ("title", title),
                ("author", author),
                ("format", format),
                ("composer", composer),
                ("arranger", arranger),
                ("number_parts", number_parts),
                ("number_measures", number_measures),
                ("key_signature", key_signature),
                ("tempo", tempo),
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
        """Extract specific measures and/or parts from a score."""
        return extract_sections(
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
        """Analyze a score and report requested metrics."""
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


def main(argv: Sequence[str] | None = None) -> None:
    """Entrypoint used by the console script."""
    command = list(argv) if argv is not None else sys.argv[1:]
    fire.Fire(ScoreTool, command=command)


if __name__ == "__main__":
    main()

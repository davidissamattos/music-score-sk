"""Score analysis utilities with individual metric functions."""

from __future__ import annotations

from collections import OrderedDict, Counter
from statistics import mean
from typing import Any, Callable, Dict, List

from music21 import key as m21_key
from music21 import note as m21_note
from music21 import pitch as m21_pitch

from .utils import load_score


def analyze_score(
    *,
    source: str | None = None,
    stdin_data: bytes | None = None,
    metrics: list[str] | None = None,
) -> str:
    """Return requested analysis metrics for a score."""
    score = load_score(source, stdin_data=stdin_data)
    requested = metrics or list(_METRIC_FUNCTIONS.keys())
    invalid = [name for name in requested if name not in _METRIC_FUNCTIONS]
    if invalid:
        raise ValueError(
            f"Unsupported metric(s): {', '.join(invalid)}. "
            f"Available: {', '.join(_METRIC_FUNCTIONS)}"
        )

    lines: list[str] = []
    for name in requested:
        label = _METRIC_LABELS.get(name, name.replace("_", " ").title())
        func = _METRIC_FUNCTIONS[name]
        try:
            value = func(score)
        except Exception:
            value = "N/A"
        lines.append(f"{label}: {value}")
    return "\n".join(lines)


# Helpers --------------------------------------------------------------------


def _score_stats(score) -> dict[str, Any]:
    """Cache basic stats on the score object."""
    cache_name = "_analysis_stats"
    cached = getattr(score, cache_name, None)
    if cached is not None:
        return cached
    notes = [n for n in score.recurse().notes if isinstance(n, m21_note.Note)]
    pitches = [n.pitch.midi for n in notes if n.pitch is not None]
    durations = [n.quarterLength for n in notes if n.quarterLength]
    stats = {
        "notes": notes,
        "pitches": pitches,
        "durations": durations,
        "pitch_classes": [n.pitch.pitchClass for n in notes if n.pitch],
        "total_time": sum(durations),
    }
    setattr(score, cache_name, stats)
    return stats


def _entropy(values: List[int]) -> float:
    if not values:
        return 0.0
    freq = Counter(values)
    total = sum(freq.values())
    probabilities = [count / total for count in freq.values()]
    from math import log2

    return round(-sum(p * log2(p) for p in probabilities if p > 0), 4)


def _average_tempo(score) -> float | None:
    try:
        tempos = [
            boundary[2].number
            for boundary in score.metronomeMarkBoundaries()
            if boundary[2] is not None and hasattr(boundary[2], "number")
        ]
        return round(mean(tempos), 2) if tempos else None
    except Exception:
        return None


def _gather_key_signatures(score) -> str | None:
    signatures = []
    for ks in score.recurse().getElementsByClass("KeySignature"):
        try:
            name = ks.asKey().name
        except Exception:
            name = None
        if name and name not in signatures:
            signatures.append(name)
    return ", ".join(signatures) if signatures else None


def _gather_time_signatures(score) -> str | None:
    seen = []
    for ts in score.recurse().getElementsByClass("TimeSignature"):
        ratio = getattr(ts, "ratioString", None)
        if ratio and ratio not in seen:
            seen.append(ratio)
    return ", ".join(seen) if seen else None


def _compute_difficulty(score) -> float | None:
    interval_entropy = metric_interval_entropy(score)
    note_density = metric_note_density(score)
    npvi = metric_npvi(score)
    if note_density in ("N/A", None):
        note_density_value = None
    else:
        note_density_value = float(note_density)
    if any(value is None or value == "N/A" for value in [interval_entropy, note_density_value, npvi]):
        return None
    weights = {"interval_entropy": 0.34, "note_density": 0.58, "npvi": 0.21}
    intercept = 0.47
    difficulty = intercept
    difficulty += weights["interval_entropy"] * float(interval_entropy)
    difficulty += weights["note_density"] * note_density_value
    difficulty += weights["npvi"] * float(npvi)
    return round(difficulty, 4)


def _categorize(value: float | None, thresholds: tuple[float, float], labels: tuple[str, str, str]):
    if value is None:
        return "unknown"
    try:
        val = float(value)
    except (TypeError, ValueError):
        return "unknown"
    low, high = thresholds
    low_label, mid_label, high_label = labels
    if val <= low:
        return low_label
    if val <= high:
        return mid_label
    return high_label


def _difficulty_categories(score) -> str:
    highest = metric_highest_note(score)
    rhythmic_variety = metric_rhythmic_variety(score)
    avg_duration = metric_avg_duration(score)
    key_signature = metric_key_signature(score)
    number_of_notes = metric_number_of_notes(score)
    time_signature = metric_time_signature(score)
    interval_entropy = metric_interval_entropy(score)
    note_density = metric_note_density(score)
    npvi = metric_npvi(score)
    difficulty = metric_difficulty(score)

    def highest_note_category():
        if not highest:
            return "unknown"
        try:
            midi = m21_pitch.Pitch(highest).midi
        except Exception:
            return "unknown"
        if midi <= m21_pitch.Pitch("E-5").midi:
            return "beginner"
        if midi <= m21_pitch.Pitch("G5").midi:
            return "intermediate"
        return "advanced"

    def key_signature_category():
        if not key_signature:
            return "unknown"
        key_name = key_signature.split(",")[0].strip()
        if not key_name:
            return "unknown"
        try:
            signature = m21_key.Key(key_name)
            accidentals = abs(signature.sharps)
        except Exception:
            return "unknown"
        if accidentals <= 1:
            return "low"
        if accidentals <= 3:
            return "medium"
        return "high"

    categories = OrderedDict(
        [
            ("highest_note_category", highest_note_category()),
            ("rhythmic_variety_category", _categorize(rhythmic_variety, (2, 4), ("low", "medium", "high"))),
            ("avg_duration_category", _categorize(avg_duration, (0.5, 1.0), ("fast", "moderate", "slow"))),
            ("key_signature_category", key_signature_category()),
            ("number_of_notes_category", _categorize(number_of_notes, (50, 150), ("low", "medium", "high"))),
            ("time_signature_category", "low" if time_signature and time_signature.startswith(("2/4", "3/4", "4/4")) else "high"),
            ("interval_entropy_category", _categorize(interval_entropy, (1.0, 2.0), ("low", "medium", "high"))),
            ("note_density_category", _categorize(note_density, (2, 5), ("low", "medium", "high"))),
            ("npvi_category", _categorize(npvi, (20, 40), ("low", "medium", "high"))),
            ("difficulty_category", _categorize(difficulty, (1.5, 2.5), ("beginner", "intermediate", "advanced"))),
        ]
    )
    return ", ".join(f"{k}={v}" for k, v in categories.items())


# Metric implementations ------------------------------------------------------


def metric_title(score) -> str:
    return score.metadata.title if score.metadata and score.metadata.title else "Unknown"


def metric_key(score) -> str:
    analyzed = score.analyze("key")
    return f"{analyzed.tonic.name} {analyzed.mode}".replace("-", "b")


def metric_key_clarity(score) -> float:
    stats = _score_stats(score)
    if not stats["pitch_classes"]:
        return 0.0
    analyzed = score.analyze("key")
    scale_pcs = {p.pitchClass for p in analyzed.getPitches()}
    in_key = sum(1 for pc in stats["pitch_classes"] if pc in scale_pcs)
    return round(in_key / len(stats["pitch_classes"]), 4)


def metric_interval_entropy(score) -> float:
    stats = _score_stats(score)
    intervals = [abs(b - a) for a, b in zip(stats["pitches"][:-1], stats["pitches"][1:])]
    return _entropy(intervals)


def metric_pitch_class_entropy(score) -> float:
    stats = _score_stats(score)
    return _entropy(stats["pitch_classes"])


def metric_npvi(score) -> float:
    stats = _score_stats(score)
    durations = stats["durations"]
    pairs = list(zip(durations[:-1], durations[1:]))
    if not pairs:
        return 0.0
    diffs = [abs(d1 - d2) / ((d1 + d2) / 2) for d1, d2 in pairs if (d1 + d2)]
    return round(100 * (sum(diffs) / len(diffs)), 2) if diffs else 0.0


def metric_contour_complexity(score) -> float:
    stats = _score_stats(score)
    pitches = stats["pitches"]
    if len(pitches) < 3:
        return 0.0
    directions = []
    for prev, curr in zip(pitches[:-1], pitches[1:]):
        delta = curr - prev
        directions.append(0 if delta == 0 else (1 if delta > 0 else -1))
    changes = sum(
        1
        for a, b in zip(directions[:-1], directions[1:])
        if a != 0 and b != 0 and a != b
    )
    return round(changes / (len(pitches) - 2), 4)


def metric_highest_note(score) -> str:
    stats = _score_stats(score)
    highest = "Unknown"
    for candidate in stats["notes"]:
        if candidate.pitch is None:
            continue
        if highest == "Unknown" or candidate.pitch.midi > m21_pitch.Pitch(highest).midi:
            highest = candidate.pitch.nameWithOctave.replace("-", "b")
    return highest


def metric_rhythmic_variety(score) -> int:
    stats = _score_stats(score)
    return len(set(stats["durations"]))


def metric_avg_duration(score) -> float:
    stats = _score_stats(score)
    return round(mean(stats["durations"]), 4) if stats["durations"] else 0.0


def metric_number_of_notes(score) -> int:
    stats = _score_stats(score)
    return len(stats["notes"])


def metric_key_signature(score) -> str | None:
    return _gather_key_signatures(score)


def metric_time_signature(score) -> str | None:
    return _gather_time_signatures(score)


def metric_pitch_range(score) -> int | None:
    stats = _score_stats(score)
    return max(stats["pitches"]) - min(stats["pitches"]) if stats["pitches"] else None


def metric_articulation_density(score) -> float:
    stats = _score_stats(score)
    total = sum(len(n.articulations) for n in stats["notes"])
    return round(total / len(stats["notes"]), 4) if stats["notes"] else 0.0


def metric_note_density(score) -> float | None:
    stats = _score_stats(score)
    total_time = stats["total_time"]
    return round(len(stats["notes"]) / total_time, 4) if total_time else None


def metric_avg_tempo(score) -> float | None:
    return _average_tempo(score)


def metric_dynamic_range(score) -> int:
    dynamics = {
        getattr(dynamic, "value", str(dynamic))
        for dynamic in score.recurse().getElementsByClass("Dynamic")
    }
    return len(dynamics)


def metric_difficulty(score) -> float | None:
    return _compute_difficulty(score)


def metric_difficulty_categories(score) -> str:
    return _difficulty_categories(score)


_METRIC_FUNCTIONS: OrderedDict[str, Callable[[Any], Any]] = OrderedDict(
    [
        ("title", metric_title),
        ("key", metric_key),
        ("key_clarity", metric_key_clarity),
        ("interval_entropy", metric_interval_entropy),
        ("pitch_class_entropy", metric_pitch_class_entropy),
        ("npvi", metric_npvi),
        ("contour_complexity", metric_contour_complexity),
        ("highest_note", metric_highest_note),
        ("rhythmic_variety", metric_rhythmic_variety),
        ("avg_duration", metric_avg_duration),
        ("number_of_notes", metric_number_of_notes),
        ("key_signature", metric_key_signature),
        ("time_signature", metric_time_signature),
        ("pitch_range", metric_pitch_range),
        ("articulation_density", metric_articulation_density),
        ("note_density", metric_note_density),
        ("avg_tempo", metric_avg_tempo),
        ("dynamic_range", metric_dynamic_range),
        ("difficulty", metric_difficulty),
        ("difficulty_categories", metric_difficulty_categories),
    ]
)

_METRIC_LABELS: OrderedDict[str, str] = OrderedDict(
    [
        ("title", "Title"),
        ("key", "Key"),
        ("key_clarity", "Key Clarity Index"),
        ("interval_entropy", "Interval Entropy"),
        ("pitch_class_entropy", "Pitch Class Entropy"),
        ("npvi", "nPVI"),
        ("contour_complexity", "Contour Complexity"),
        ("highest_note", "Highest Note"),
        ("rhythmic_variety", "Rhythmic Variety"),
        ("avg_duration", "Average Duration"),
        ("number_of_notes", "Number of Notes"),
        ("key_signature", "Key Signature"),
        ("time_signature", "Time Signature"),
        ("pitch_range", "Pitch Range"),
        ("articulation_density", "Articulation Density"),
        ("note_density", "Note Density"),
        ("avg_tempo", "Average Tempo"),
        ("dynamic_range", "Dynamic Range"),
        ("difficulty", "Difficulty Score"),
        ("difficulty_categories", "Difficulty Categories"),
    ]
)

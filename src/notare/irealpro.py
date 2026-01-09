"""iReal Pro URL builder.

Converts a score into an iReal Pro custom chord chart URL.

Steps
- Checks if the score contains chords; aborts if none are found.
- Extracts chords-only view implicitly by scanning measures and collecting
  chord objects.
- Builds the iReal Pro URL according to the protocol and percent-encodes
  it for HTML/browser safety.
"""

from __future__ import annotations

from typing import Iterable
from urllib.parse import quote

from music21 import stream as m21_stream
from music21 import chord as m21_chord
from music21 import meter as m21_meter
from music21 import harmony as m21_harmony

from .utils import load_score


def _title_for_ireal(title: str) -> str:
    t = (title or "").strip()
    if not t:
        return "Untitled"
    # Move leading "The" to end for sorting purposes
    if t.lower().startswith("the "):
        return f"{t[4:]}, The"
    return t


def _composer_last_first(composer: str) -> str:
    name = (composer or "").strip()
    if not name:
        return "Unknown"
    parts = name.split()
    if len(parts) == 1:
        return parts[0]
    last = parts[-1]
    first = " ".join(parts[:-1])
    return f"{last} {first}".strip()


def _detect_time_signature(stream_obj: m21_stream.Stream) -> str | None:
    """Return iReal Pro time signature token like 'T44', if found."""
    try:
        ts = next(iter(stream_obj.recurse().getElementsByClass(m21_meter.TimeSignature)), None)
    except Exception:
        ts = None
    if not ts:
        return None
    try:
        num = int(ts.numerator)
        den = int(ts.denominator)
        return f"T{num}{den}"
    except Exception:
        return None


def _detect_key_token(stream_obj: m21_stream.Stream) -> str:
    """Return iReal Pro key token (e.g., 'C', 'F#-', 'Bb-'). Best-effort."""
    try:
        k = stream_obj.analyze("key")
        name = getattr(k, "name", "") or ""
    except Exception:
        name = ""
    if not name:
        return "C"  # default
    name = name.strip()
    # Examples: "C major", "F# minor", "Bb major"
    is_minor = "minor" in name.lower()
    tonic = name.split()[0]
    # Normalize music21 flats '-' to 'b'
    tonic = tonic.replace("-", "b")
    return f"{tonic}-" if is_minor else tonic


def _measure_chords(measure: m21_stream.Measure) -> list[str]:
    """Extract chord tokens for a measure.

    Best-effort: outputs only root note names (no quality/inversion), e.g.,
    'C', 'G', 'Bb'. This keeps the implementation simple while producing a
    valid iReal Pro progression.
    """
    tokens: list[str] = []
    # Prefer chord symbols if present (Harmony / ChordSymbol)
    for el in measure.recurse().getElementsByClass(m21_harmony.ChordSymbol):
        try:
            fig = (getattr(el, "figure", None) or "").strip()
        except Exception:
            fig = ""
        token = None
        if fig:
            token = fig.replace("-", "b")  # normalize flats for URL
        else:
            # fallback to root + quality
            try:
                root = el.root()
                quality = getattr(el, "kind", None) or ""
                token = f"{root.name}{quality}".strip()
            except Exception:
                token = None
        # Append inversion if available
        try:
            bass = el.bass()
            if token and bass and getattr(bass, "name", None):
                token = f"{token}/{bass.name.replace('-', 'b')}"
        except Exception:
            pass
        if token:
            tokens.append(token)

    # Also collect stacked note chords
    for el in measure.getElementsByClass(m21_chord.Chord):
        root_token = None
        # Try common root accessors
        try:
            rp = el.root()
            if rp and getattr(rp, "name", None):
                root_token = rp.name
        except Exception:
            pass
        if not root_token:
            try:
                rp = getattr(el, "rootNote", None)
                if rp and getattr(rp, "name", None):
                    root_token = rp.name
            except Exception:
                pass
        if not root_token:
            # Fallback: lowest note name
            try:
                el.sortAscending()
                lowest = el.pitches[0]
                root_token = lowest.name
            except Exception:
                root_token = None
        if root_token:
            # Convert flats from '-' to 'b' for URL
            tokens.append(root_token.replace("-", "b"))
    return tokens


def _build_progression(part: m21_stream.Stream) -> str:
    """Build iReal Pro chord progression from a single part/stream."""
    lines: list[str] = []
    ts_token = _detect_time_signature(part)
    if ts_token:
        lines.append(ts_token)
    measures = list(part.getElementsByClass(m21_stream.Measure))
    for idx, meas in enumerate(measures):
        chords = _measure_chords(meas)
        if idx == 0 and not lines:
            # no TS token; start directly
            pass
        # Separate chords within measure with space (cells), end measure with '|'
        if chords:
            lines.append(" ".join(chords))
        # Always place a barline even for empty measures to preserve structure
        lines.append("|")
    # Replace last '|' with final bar 'Z' if any measures exist
    if lines:
        # Ensure final thick double bar
        if lines[-1] == "|":
            lines[-1] = "Z"
        else:
            lines.append("Z")
    return " ".join(lines).strip()


def score_to_irealpro_url(
    *,
    source: str | None = None,
    style: str | None = None,
) -> str:
    """Convert a score into an HTML-safe iReal Pro URL and return it.

    - Aborts with ValueError if no chords are present in the score.
    - Uses first part containing chords when multiple parts exist.
    - Percent-encodes the resulting URL for safe embedding in HTML.
    """
    score = load_score(source)

    # Find parts/targets and whether chords exist
    targets: Iterable[m21_stream.Stream] = list(score.parts) or [score]
    part_with_chords: m21_stream.Stream | None = None
    for p in targets:
        try:
            if any(isinstance(el, m21_chord.Chord) for el in p.recurse().getElementsByClass(m21_chord.Chord)):
                part_with_chords = p
                break
        except Exception:
            continue

    if part_with_chords is None:
        raise ValueError("No chords found in the score.")

    # Header components: Title, Composer (Last First), Style, Key, n
    meta = getattr(score, "metadata", None)
    title = _title_for_ireal(getattr(meta, "title", None) or "")
    composer = _composer_last_first(getattr(meta, "composer", None) or "")
    style_text = (style or "Unknown").strip() or "Unknown"
    key_token = _detect_key_token(score)

    progression = _build_progression(part_with_chords)
    if not progression:
        # If measures exist but progression ended empty, treat as no chords
        raise ValueError("No chords found in the score.")

    raw_url = f"irealbook://{title}={composer}={style_text}={key_token}=n={progression}"
    return quote(raw_url, safe="")


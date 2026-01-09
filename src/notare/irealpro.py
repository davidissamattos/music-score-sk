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
from urllib.parse import quote, unquote
import html as _html

from music21 import stream as m21_stream
from music21 import chord as m21_chord
from music21 import meter as m21_meter
from music21 import harmony as m21_harmony
from music21 import bar as m21_bar
from music21 import expressions as m21_expr

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
    symbol_tokens: list[str] = []
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
        # Append textual modifiers such as "alter b5", "add b13" if present
        try:
            kind_obj = getattr(el, "kind", None)
            modifier = None
            if kind_obj is not None:
                modifier = getattr(kind_obj, "text", None) or getattr(el, "kindText", None)
            if token and modifier:
                mod = str(modifier).strip()
                if mod and mod not in token:
                    token = f"{token} {mod}"
        except Exception:
            pass
        # Append inversion if available, but skip when bass equals root
        try:
            bass = el.bass()
            root_obj = el.root()
            root_name = None
            if root_obj and getattr(root_obj, "name", None):
                root_name = root_obj.name.replace("-", "b")
            bass_name = None
            if bass and getattr(bass, "name", None):
                bass_name = bass.name.replace("-", "b")
            if token and bass_name:
                # If figure already contains a slash, keep as-is
                if "/" not in token:
                    # Only append when bass differs from root
                    if not root_name or bass_name.lower() != (root_name or "").lower():
                        token = f"{token}/{bass_name}"
        except Exception:
            pass
        if token:
            symbol_tokens.append(token)

    # If chord symbols exist, use them exclusively to avoid duplicates
    if symbol_tokens:
        # Deduplicate while preserving order
        seen: set[str] = set()
        for t in symbol_tokens:
            if t not in seen:
                tokens.append(t)
                seen.add(t)
        return tokens

    # Otherwise collect stacked note chords
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
            tok = root_token.replace("-", "b")
            if tok not in tokens:
                tokens.append(tok)
    return tokens


def _build_progression(part: m21_stream.Stream) -> str:
    """Build iReal Pro chord progression from a single part/stream.

    Handles:
    - Time signature token changes (`Txx`) when detected at measure start
    - Repeat barlines: `{` on forward repeat, `}` on backward repeat
    - Double barlines: `[` opening, `]` closing
    - Rehearsal marks: `*A`, `*B`, `*C` (appears before measure content)
    - Endings: `N1`, `N2`, `N3` when detected via simple direction words like `1.`
    - Staff text phrases recognized by iReal Pro: `<D.C. al Fine>`, `<D.C. al Coda>`, `<D.S. al Fine>`, `<D.S. al Coda>`, `<Fine>`, `<Coda>`
    """
    lines: list[str] = []
    # initial global time signature (if present on part/score)
    last_ts: str | None = _detect_time_signature(part)
    if last_ts:
        lines.append(last_ts)
    measures = list(part.getElementsByClass(m21_stream.Measure))

    # Note: do not pre-append globally collected staff text (DC/DS/Coda/Fine)
    # to avoid a flurry of tokens before the first chord. We'll detect and
    # emit these per-measure only.

    def _ts_for_measure(m: m21_stream.Measure) -> str | None:
        try:
            ts = next(iter(m.getElementsByClass(m21_meter.TimeSignature)), None)
        except Exception:
            ts = None
        if not ts:
            return None
        try:
            return f"T{int(ts.numerator)}{int(ts.denominator)}"
        except Exception:
            return None

    def _rehearsal_token(m: m21_stream.Measure) -> str | None:
        try:
            rm = next(iter(m.recurse().getElementsByClass(m21_expr.RehearsalMark)), None)
        except Exception:
            rm = None
        if not rm:
            return None
        label = (getattr(rm, "mark", None) or getattr(rm, "content", None) or "").strip()
        if not label:
            return None
        # Use first char if single-letter A/B/C; otherwise skip
        ch = label[0].upper()
        if ch.isalpha():
            return f"*{ch}"
        return None

    def _ending_token(m: m21_stream.Measure) -> str | None:
        # simplistic detection: look for words like "1.", "2." in directions
        candidates: list[str] = []
        try:
            for t in m.recurse():
                # collect any textual content from common attributes
                for attr in ("content", "text", "mark", "words"):
                    try:
                        v = getattr(t, attr)
                    except Exception:
                        v = None
                    if v:
                        candidates.append(str(v))
        except Exception:
            pass
        for content in candidates:
            c = (content or "").strip()
            if c.startswith("1"):
                return "N1"
            if c.startswith("2"):
                return "N2"
            if c.startswith("3"):
                return "N3"
        return None

    def _staff_text_tokens(m: m21_stream.Measure) -> list[str]:
        tokens: list[str] = []
        recognized = {
            "D.C. al Fine": "<D.C. al Fine>",
            "DC al Fine": "<D.C. al Fine>",
            "D.C. al Coda": "<D.C. al Coda>",
            "DC al Coda": "<D.C. al Coda>",
            "D.S. al Fine": "<D.S. al Fine>",
            "DS al Fine": "<D.S. al Fine>",
            "D.S. al Coda": "<D.S. al Coda>",
            "DS al Coda": "<D.S. al Coda>",
            "Fine": "<Fine>",
            "Coda": "<Coda>",
        }
        # Search broadly across measure elements
        try:
            for t in m.recurse():
                content = None
                # Collect text-like attributes commonly used across music21 objects
                for attr in ("content", "text", "mark", "words"):
                    try:
                        v = getattr(t, attr)
                    except Exception:
                        v = None
                    if v:
                        content = str(v)
                        break
                if not content:
                    try:
                        content = str(t)
                    except Exception:
                        content = None
                if not content:
                    continue
                lc = content.lower()
                for key, token in recognized.items():
                    if key.lower() in lc:
                        tokens.append(token)
        except Exception:
            pass
        # Deduplicate per-measure while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for tok in tokens:
            if tok not in seen:
                unique.append(tok)
                seen.add(tok)
        return unique

    def _barline_tokens(m: m21_stream.Measure) -> tuple[list[str], list[str]]:
        """Return (prefix, suffix) tokens based on barlines in the measure.

        Handles both generic Barline objects and Repeat objects, which
        music21 creates for forward/backward repeats.
        """
        prefix: list[str] = []
        suffix: list[str] = []
        # Collect all barlines and track location hints
        bars: list[tuple[object, str | None]] = []
        try:
            for bl in m.getElementsByClass(m21_bar.Barline):
                bars.append((bl, _norm_lower(getattr(bl, "location", None)) or None))
            # Repeat objects appear separately from generic Barline
            for rep in m.getElementsByClass(m21_bar.Repeat):
                bars.append((rep, _norm_lower(getattr(rep, "location", None)) or None))
        except Exception:
            pass
        # Also consider explicit left/right barline attributes on the measure
        lb = None
        rb = None
        try:
            lb = getattr(m, "leftBarline", None)
        except Exception:
            lb = None
        try:
            rb = getattr(m, "rightBarline", None)
        except Exception:
            rb = None
        if lb:
            bars.append((lb, "left"))
        if rb:
            bars.append((rb, "right"))

        def _norm_lower(value: object) -> str:
            if value is None:
                return ""
            # Prefer 'name' or 'value' attribute when present (enums)
            for attr in ("name", "value"):
                try:
                    v = getattr(value, attr)
                except Exception:
                    v = None
                if v is not None:
                    try:
                        return str(v).lower()
                    except Exception:
                        pass
            try:
                return str(value).lower()
            except Exception:
                return ""
        def _norm_style(style: str) -> str:
            s = (style or "").lower()
            # Normalize common enum string forms to hyphenated style names
            s = s.replace("barlinestyle.", "")
            s = s.replace("_", "-")
            return s
        def _norm_location(loc: str) -> str:
            l = (loc or "").lower()
            l = l.replace("barlinelocation.", "")
            return l
        for bl, loc_hint in bars:
            style = _norm_style(_norm_lower(getattr(bl, "style", None)))
            loc = _norm_location(loc_hint or _norm_lower(getattr(bl, "location", None)))
            # For Repeat objects, the object itself carries the 'direction'
            repeat_dir = ""
            try:
                # Prefer direct direction attribute when present
                direct_dir = getattr(bl, "direction", None)
                repeat_dir = _norm_lower(direct_dir) if direct_dir is not None else ""
            except Exception:
                repeat_dir = ""
            if not repeat_dir:
                # Some Barline objects carry a nested 'repeat' with direction
                try:
                    repeat_obj = getattr(bl, "repeat", None)
                    repeat_dir = _norm_lower(getattr(repeat_obj, "direction", None))
                except Exception:
                    repeat_dir = ""
            # Forward repeat
            if loc == "left" and (repeat_dir in {"forward", "start"} or style == "heavy-light"):
                if "{" not in prefix:
                    prefix.append("{")
            # Opening double bar
            if loc == "left" and style == "light-light":
                if "[" not in prefix:
                    prefix.append("[")
            # Backward repeat
            if loc == "right" and (repeat_dir in {"backward", "end"} or style == "light-heavy"):
                if "}" not in suffix:
                    suffix.append("}")
            # Closing double bar
            if loc == "right" and style == "light-light":
                if "]" not in suffix:
                    suffix.append("]")
        return (prefix, suffix)

    # Pre-scan for ending measures to provide a fallback repeat region when barlines are not parsed
    ending_indices: list[int] = []
    backward_repeat_index: int = -1
    try:
        for i, m in enumerate(measures):
            et = None
            # Lightweight local ending detection (duplicated logic to avoid recursion cost)
            try:
                candidates: list[str] = []
                for t in m.recurse():
                    for attr in ("content", "text", "mark", "words"):
                        try:
                            v = getattr(t, attr)
                        except Exception:
                            v = None
                        if v:
                            candidates.append(str(v))
                for content in candidates:
                    c = (content or "").strip()
                    if c.startswith("1") or c.startswith("2") or c.startswith("3"):
                        et = True
                        break
                # Track first backward repeat via Repeat objects when text isn't present
                if backward_repeat_index < 0:
                    try:
                        reps = list(m.getElementsByClass(m21_bar.Repeat))
                        for rep in reps:
                            dir = str(getattr(rep, "direction", "")).lower()
                            loc = str(getattr(rep, "location", "")).lower()
                            if dir in {"end", "backward"} and loc == "right":
                                backward_repeat_index = i
                                break
                    except Exception:
                        pass
            except Exception:
                pass
            if et:
                ending_indices.append(i)
    except Exception:
        ending_indices = []
    fallback_repeat_needed = len(ending_indices) > 0
    first_ending_index = ending_indices[0] if ending_indices else -1
    added_forward_repeat = False
    added_backward_repeat = False

    # If no explicit ending texts were found but a backward repeat exists,
    # synthesize sequential ending markers (N1, N2, ...) for following measures
    synthetic_endings: dict[int, str] = {}
    if not ending_indices and backward_repeat_index >= 0:
        n = 1
        j = backward_repeat_index + 1
        while j < len(measures):
            synthetic_endings[j] = f"N{n}"
            n += 1
            # Stop when encountering a strong final barline on the right
            try:
                rb = getattr(measures[j], "rightBarline", None)
                if rb is not None:
                    rbt = str(getattr(rb, "type", "")).lower()
                    if "final" in rbt:
                        break
            except Exception:
                pass
            j += 1

    for idx, meas in enumerate(measures):
        # time signature change
        ts_here = _ts_for_measure(meas)
        if ts_here and ts_here != last_ts:
            lines.append(ts_here)
            last_ts = ts_here

        # rehearsal marks and endings
        reh = _rehearsal_token(meas)
        if reh:
            lines.append(reh)
        ending_tok = _ending_token(meas)
        if not ending_tok and synthetic_endings.get(idx):
            ending_tok = synthetic_endings[idx]
        if ending_tok:
            lines.append(ending_tok)

        # staff text phrases
        for st in _staff_text_tokens(meas):
            lines.append(st)

        # barline-derived wrappers
        pre, post = _barline_tokens(meas)
        if "{" in pre:
            added_forward_repeat = True
        if "}" in post:
            added_backward_repeat = True

        # Fallback: if endings exist but no explicit barline repeats parsed, add braces
        if fallback_repeat_needed:
            if not added_forward_repeat and idx == 0:
                pre.append("{")
                added_forward_repeat = True
            if not added_backward_repeat and first_ending_index >= 1 and idx == (first_ending_index - 1):
                post.append("}")
                added_backward_repeat = True
        for p in pre:
            lines.append(p)

        # chords within measure
        chords = _measure_chords(meas)
        if idx == 0 and not lines:
            pass
        if chords:
            lines.append(" ".join(chords))
        # end measure barline
        lines.append("|")

        # suffix after measure barline
        for p in post:
            lines.append(p)

    # ensure final thick double bar: always replace the last '|' with 'Z'
    # even if suffix tokens (like '}' or ']') were appended after it.
    if lines:
        last_bar_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i] == "|":
                last_bar_idx = i
                break
        if last_bar_idx >= 0:
            lines[last_bar_idx] = "Z"
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


def score_to_irealpro_html_link(
    *,
    source: str | None = None,
    style: str | None = None,
) -> str:
    """Return an HTML anchor tag pointing to the iReal Pro URL.

    The `href` is percent-encoded for browser safety; the link text uses the
    normalized title and is HTML-escaped.
    """
    # Build the encoded URL first (this will consume stdin if used)
    url = score_to_irealpro_url(source=source, style=style)
    # Derive the title from the URL to avoid reading stdin a second time
    decoded = unquote(url)
    # Extract title: irealbook://<title>=<composer>=<style>=<key>=n=<progression>
    try:
        payload = decoded[len("irealbook://") :]
        title = payload.split("=", 1)[0] or "Untitled"
    except Exception:
        title = "Untitled"
    return f'<a href="{url}">{_html.escape(title)}</a>'


def score_to_irealpro_raw_url(
    *,
    source: str | None = None,
    style: str | None = None,
) -> str:
    """Return a raw (not percent-encoded) iReal Pro custom URL string."""
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

    meta = getattr(score, "metadata", None)
    title = _title_for_ireal(getattr(meta, "title", None) or "")
    composer = _composer_last_first(getattr(meta, "composer", None) or "")
    style_text = (style or "Unknown").strip() or "Unknown"
    key_token = _detect_key_token(score)

    progression = _build_progression(part_with_chords)
    if not progression:
        # If measures exist but progression ended empty, treat as no chords
        raise ValueError("No chords found in the score.")

    return f"irealbook://{title}={composer}={style_text}={key_token}=n={progression}"


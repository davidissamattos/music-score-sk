import re
import urllib.parse as _up
from pathlib import Path

import pytest

from notare.irealpro import score_to_irealpro_url, score_to_irealpro_raw_url
from notare.utils import load_score
from music21 import stream as m21_stream
from music21 import harmony as m21_harmony
from music21 import bar as m21_bar


DATA_DIR = Path("tests/data/irealpro").resolve()


def _extract_href_from_html(html_path: Path) -> str:
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    # Find first href attribute containing irealbook scheme
    m = re.search(r'href="([^"]+)"', text, flags=re.IGNORECASE)
    if not m:
        raise AssertionError(f"No href found in {html_path}")
    href = m.group(1)
    assert href.startswith("irealbook://") or href.startswith("irealb://")
    return href


def _collect_pairs() -> list[tuple[Path, Path]]:
    if not DATA_DIR.exists():
        return []
    xmls = {p.stem: p for p in DATA_DIR.glob("*.musicxml")}
    htmls = {p.stem: p for p in DATA_DIR.glob("*.html")}
    common = sorted(set(xmls.keys()) & set(htmls.keys()))
    return [(xmls[name], htmls[name]) for name in common]


def _normalize_html_url_to_irealbook_six(href: str) -> str:
    decoded = _up.unquote(href)
    payload = decoded
    if payload.startswith("irealbook://"):
        payload = payload[len("irealbook://") :]
    elif payload.startswith("irealb://"):
        payload = payload[len("irealb://") :]

    segments = payload.split("=")
    assert len(segments) >= 5
    title = segments[0].strip()
    composer = segments[1].strip()
    # Find progression segment heuristically (contains barlines or braces)
    prog_idx = None
    for i, seg in enumerate(segments):
        s = seg.strip()
        if any(tok in s for tok in ("|", "Z", "{", "}", "[", "]")) and i >= 3:
            prog_idx = i
            break
    assert prog_idx is not None, "Progression segment not found in HTML URL"
    progression = segments[prog_idx].strip()

    # Identify key as nearest preceding segment matching musical key token
    key_idx = None
    key_re = re.compile(r"^[A-G](?:b|#)?(?:-)?$")
    for i in range(prog_idx - 1, 1, -1):
        if key_re.match(segments[i].strip()):
            key_idx = i
            break
    assert key_idx is not None, "Key segment not found in HTML URL"
    key = segments[key_idx].strip()

    # Style is the nearest non-empty segment before key
    style = "Unknown"
    for i in range(key_idx - 1, 1, -1):
        cand = segments[i].strip()
        if cand:
            style = cand
            break

    normalized = f"irealbook://{title}={composer}={style}={key}=n={progression}"
    return normalized


@pytest.mark.parametrize("xml_path, html_path", _collect_pairs())
def test_irealpro_conversion_matches_html_url(xml_path: Path, html_path: Path):
    href = _extract_href_from_html(html_path)
    expected_decoded = _normalize_html_url_to_irealbook_six(href)

    # Build URLs from our converter using the style extracted from HTML
    parts = expected_decoded[len("irealbook://") :].split("=")
    _, _, style, _, n_token, progression = parts
    assert n_token == "n" and progression

    encoded_url = score_to_irealpro_url(source=str(xml_path), style=style)
    decoded_url = _up.unquote(encoded_url)
    # Compare title, style, and key against HTML truth; ensure progression exists
    exp_parts = expected_decoded[len("irealbook://") :].split("=")
    got_parts = decoded_url[len("irealbook://") :].split("=")
    assert exp_parts[0] == got_parts[0]  # title
    assert exp_parts[2] == got_parts[2]  # style
    assert got_parts[3].strip() != ""     # key is present
    assert got_parts[-1].strip() != ""  # progression is non-empty

    raw_url = score_to_irealpro_raw_url(source=str(xml_path), style=style)
    assert raw_url[len("irealbook://") :].split("=")[4] != ""  # progression present in raw

    # Structural validations against the paired MusicXML export
    raw_decoded = _up.unquote(raw_url)
    progression = raw_decoded.split("=n=", 1)[1]

    def _progression_measure_count(s: str) -> int:
        return s.count("|") + (1 if "Z" in s else 0)

    def _progression_repeat_counts(s: str) -> tuple[int, int]:
        return s.count("{"), s.count("}")

    def _progression_measures_tokens(s: str) -> list[list[str]]:
        measures: list[list[str]] = []
        curr: list[str] = []
        def _is_chord(tok: str) -> bool:
            return re.match(r"^[A-G](?:b|#)?[^\s\|\{\}\[\]<>]*$", tok) is not None
        toks = s.split()
        i = 0
        while i < len(toks):
            tok = toks[i]
            if tok in {"|", "Z"}:
                measures.append(curr)
                curr = []
                i += 1
                continue
            if tok in {"{", "}", "[", "]"}:
                i += 1
                continue
            # Skip structural tokens and ending markers like N1/N2/N3,
            # but preserve the special 'N.C.' no-chord token.
            if tok == "N.C.":
                curr.append(tok)
                i += 1
                continue
            if tok.startswith("T") or tok.startswith("*") or tok.startswith("<") or re.match(r"^N\d+$", tok):
                i += 1
                continue
            if _is_chord(tok):
                base = tok
                # Attach textual modifiers like 'alter b5' or 'add b13' to the chord
                if i + 2 < len(toks) and toks[i + 1] in {"alter", "add"}:
                    mod_word = toks[i + 1]
                    mod_val = toks[i + 2]
                    # Ensure the modifier value isn't a structural token
                    if mod_val not in {"|", "Z", "{", "}", "[", "]"} and not mod_val.startswith(("T", "*", "<", "N")):
                        base = f"{base} {mod_word} {mod_val}"
                        i += 3
                        curr.append(base)
                        continue
                curr.append(base)
            i += 1
        if curr:
            measures.append(curr)
        return measures

    got_measures_tokens = _progression_measures_tokens(progression)
    got_measures_count = len(got_measures_tokens)
    got_fwd, got_bwd = _progression_repeat_counts(progression)

    # Expected from MusicXML via music21
    score = load_score(str(xml_path))
    part: m21_stream.Stream = list(score.parts)[0]
    xml_measures = list(part.getElementsByClass(m21_stream.Measure))
    exp_measures_count = len(xml_measures)

    # Count repeats from explicit Repeat objects
    fwd = bwd = 0
    for m in xml_measures:
        reps = list(m.getElementsByClass(m21_bar.Repeat))
        for rep in reps:
            dir = str(getattr(rep, "direction", "")).lower()
            loc = str(getattr(rep, "location", "")).lower()
            if dir in {"start", "forward"} and loc == "left":
                fwd += 1
            if dir in {"end", "backward"} and loc == "right":
                bwd += 1

    # Extract chord symbols per measure
    def _xml_measure_tokens(m: m21_stream.Measure) -> list[str]:
        tokens: list[str] = []
        for el in m.recurse().getElementsByClass(m21_harmony.ChordSymbol):
            try:
                fig = (getattr(el, "figure", None) or "").strip()
            except Exception:
                fig = ""
            token = None
            if fig:
                token = fig.replace("-", "b")
            else:
                try:
                    root = el.root()
                    quality = getattr(el, "kind", None) or ""
                    token = f"{root.name}{quality}".strip()
                except Exception:
                    token = None
            # Append textual modifiers (e.g., alter b5, add b13) if present
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
            try:
                bass = el.bass()
                root_obj = el.root()
                root_name = None
                if root_obj and getattr(root_obj, "name", None):
                    root_name = root_obj.name.replace("-", "b")
                bass_name = None
                if bass and getattr(bass, "name", None):
                    bass_name = bass.name.replace("-", "b")
                if token and bass_name and "/" not in token:
                    if not root_name or bass_name.lower() != (root_name or "").lower():
                        token = f"{token}/{bass_name}"
            except Exception:
                pass
            if token:
                tokens.append(token)
        # Deduplicate per measure
        seen: set[str] = set()
        uniq: list[str] = []
        for t in tokens:
            if t not in seen:
                uniq.append(t)
                seen.add(t)
        return uniq

    exp_measures_tokens = [_xml_measure_tokens(m) for m in xml_measures]

    # Assertions
    assert got_measures_count == exp_measures_count
    assert got_fwd == fwd and got_bwd == bwd
    # Compare chord sequences measure-by-measure
    assert len(got_measures_tokens) == exp_measures_count
    for i in range(exp_measures_count):
        assert got_measures_tokens[i] == exp_measures_tokens[i]

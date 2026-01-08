from __future__ import annotations

import platform
import subprocess
import sys
import shutil
from pathlib import Path
import re
import pytest

OUTPUT_MUSICXML_MODULES = [
    "extract",
    "insert",
    "delete",
    "simplify",
    "convert",
    "transpose",
    "set-metadata",
    "set-part-metadata",
    "delete-lyrics",
    "delete-annotations",
    "delete-fingering",
    "delete-chords",
]
OUTPUT_TEXT_MODULES = ["analyze", "metadata"]
OUTPUT_GUI_MODULES = ["show", "play"]
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "tests" / "data"
# ---- User-defined POSIX-like pipeline commands ----
# These are provided in Linux/macOS style; the tests adapt them to Windows cmd/PowerShell automatically.
PIPELINE_POSIX: list[str] = [
    'cat tests/data/MozartPianoSonata.musicxml | notare extract --measures "1,3"',
    'cat tests/data/MozartPianoSonata.musicxml | notare set-metadata --composer "J. Doe" | notare metadata --composer',
    'cat tests/data/c_scale.abc | notare convert --format musicxml',
    'cat tests/data/MozartPianoSonata.musicxml | notare simplify --ornament-removal',
    'cat tests/data/sozinho.musicxml | notare delete-lyrics',
    'cat tests/data/sozinho.musicxml | notare delete-chords',
]

def _resolve_notare_invocation(shell: str) -> str:
    """Prefer the installed `notare` command, fallback to `python -m notare.cli`.

    Returns a shell-fragment ready to be concatenated in pipelines.
    """
    exe = shutil.which("notare")
    if exe:
        if shell == "powershell":
            return f'& "{exe}"'
        return f'"{exe}"'
    py = sys.executable
    if shell == "powershell":
        return f'& "{py}" -m notare.cli'
    return f'"{py}" -m notare.cli'




def _adapt_posix_pipeline_to_shell(pipeline: str, shell: str) -> str | list[str]:
    """Convert a POSIX-style pipeline string to the current shell.

    - Replaces the leading `cat <path>` with `type` (cmd) or `Get-Content` (PowerShell).
    - Replaces every `| notare` with the resolved invocation for the shell.
    - Normalizes the path to absolute root for reliability.
    Returns a full command string for cmd/posix, or an argv list for PowerShell.
    """
    m = re.search(r"\bcat\s+([^\s|]+)", pipeline)
    if not m:
        raise AssertionError(f"Pipeline must start with 'cat <path>': {pipeline}")
    rel_path = m.group(1)
    abs_path = (REPO_ROOT / rel_path).resolve()
    inv = _resolve_notare_invocation(shell)

    # Replace all occurrences of '| notare ' using a function to avoid backslash escapes in replacement
    adapted = re.sub(r"\|\s*notare\s+", lambda _m: f"| {inv} ", pipeline)

    # Replace the 'cat <path>' with shell-specific reader and absolute path
    if shell == "cmd":
        # Use a function replacement to avoid backslash escape issues in replacement strings
        adapted = re.sub(r"\bcat\s+[^\s|]+", lambda _m: f'type "{abs_path}"', adapted, count=1)
        return adapted
    if shell == "posix":
        posix_path = str(abs_path).replace("\\", "/")
        adapted = re.sub(r"\bcat\s+[^\s|]+", lambda _m: f'cat "{posix_path}"', adapted, count=1)
        return adapted
    if shell == "powershell":
        adapted_inner = re.sub(r"\bcat\s+[^\s|]+", lambda _m: f'Get-Content "{abs_path}"', adapted, count=1)
        return ["powershell", "-NoProfile", "-Command", adapted_inner]
    raise ValueError(f"Unknown shell: {shell}")


def _detect_last_command(pipeline: str) -> str:
    """Return the last notare verb in a posix-style pipeline string.
    Example: '... | notare metadata --composer' -> 'metadata'
    """
    verbs = re.findall(r"\bnotare\s+([a-z\-]+)\b", pipeline)
    return verbs[-1] if verbs else ""


@pytest.mark.parametrize("pipeline", PIPELINE_POSIX)
def test_user_defined_posix_pipeline_runs_and_validates(pipeline: str):
    os_kind = platform.system().lower()
    shells = ["posix"] if os_kind != "windows" else ["cmd", "powershell"]
    last = _detect_last_command(pipeline)
    for shell in shells:
        cmd_or_argv = _adapt_posix_pipeline_to_shell(pipeline, shell)
        if shell == "powershell":
            cp = subprocess.run(cmd_or_argv, capture_output=True, check=True, cwd=str(REPO_ROOT))
        else:
            cp = subprocess.run(cmd_or_argv, shell=True, capture_output=True, check=True, cwd=str(REPO_ROOT))
        stdout = cp.stdout.decode(errors="replace")
        if last in OUTPUT_TEXT_MODULES:
            assert stdout.strip() != ""
        elif last in OUTPUT_MUSICXML_MODULES:
            # Expect MusicXML root element on stdout
            assert "<score-partwise" in stdout
        elif last in OUTPUT_GUI_MODULES:
            if last == "show":
                # Expect HTML root element for 'show'
                assert "<!DOCTYPE html>" in stdout or "<html" in stdout
            if last == "play":
                # Expect indication of opened MIDI file
                assert re.search(r"Opened MIDI player:\s+.*\.mid", stdout)
        else:
            # Expect MusicXML on stdout for other verbs
            raise AssertionError(f"Unhandled last command '{last}' in pipeline.")

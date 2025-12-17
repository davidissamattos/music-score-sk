# notare

A swiss knife utility for handling music score files in the command line. The aim of this cli utility is not to write music or to edit/modify music on a note level, but rather to perform bulk and scriptable transformations (e.g. extract metadata/analysis from several files). Extract the first 5 measures of 100 files and generate a pdf for then. Change the composer of multiple files

The CLI uses [Google's Python Fire](https://github.com/google/python-fire) for the CLI handling, Pytest for tests and behind the scenes most of the calculations and transformations are done with the excelent music21 library.

## Installation

### Installation from source code

Editable mode:
```bash
pip install -e .
```

### From pip

```bash
pip install notare
```

### Building the binaries

```bash
python -m build .
```

## Tests
```bash
pytest -q
```

## Usage

```bash
# Print the current version
notare version
```

### Convert

Tools for converting between different formats

```bash
# List available output formats reported by music21
notare formats

# Convert a score by specifying source, format, and optional output
notare convert --source score.musicxml --format midi --output score.mid

# When --output is omitted, data is streamed to stdout (great for pipelines)
notare convert --source score.abc --format musicxml > tmp.musicxml

# You can also request subformats exposed by music21
notare convert --source score.musicxml --format musicxml.pdf --output score.pdf
```

PDF export requires LilyPond (or MuseScore). To install LilyPond on Mac or Linux:
```bash
   sudo apt-get install lilypond   # Debian/Ubuntu
   brew install lilypond           # macOS (Homebrew)
```
To install Lilypond for Windows:

Download installer from https://lilypond.org and run it  

Then configure music21 once:
```
   python - <<'PY'
   from music21 import environment
   us = environment.UserSettings()
   us['lilypondPath'] = '/path/to/lilypond'  # e.g. C:/Program Files (x86)/LilyPond/usr/bin/lilypond.exe on Windows
   PY
```

After configuration, PDF conversions (musicxml.pdf) will succeed.

**RECOMMENDATION**

The recommended way is to use musicxml as input and output as it is the most supported

**LIMITATIONS**

- music21 does not have a ABC writer. So it does not export to ABC, but it can parse it
- music21 does not have a Lilypond parser, but it supports it as an output format

### Transpose module

```bash
# Transpose an input score by tones (use 0.5 for semitones) and write the result
# Transposition adjust the key signature by automatically identifying which is the new key and setting it appropriately
notare transpose 1 --source score.musicxml --output score_transposed.musicxml

# Limit transposition to a single part and control the resulting key signature
notare transpose -0.5 --source score.musicxml --output flute_down.musicxml --part-name Flute --key-sharps -2

# Parts can also be selected by number (1 == first part)
notare transpose 1.5 --source score.musicxml --output part2_up.mxl --part-number 2

# Stream results through pipes: omit --source to read stdin, omit --output for stdout
cat score.abc | notare convert --format musicxml | notare transpose 1 --output final.musicxml

# Emit transposed data directly to stdout in another format
notare transpose 2 --source score.musicxml --output-format midi > score.mid
```

You can also just change the key signature without transposing *in this case adding two flats

```bash
notare transpose 0 --source score.musicxml --output flute_down.musicxml --key-sharps -2
```

### Metadata module

Available metadata flags (query fields with `--field`, update with `--new-field`)

- title
- subtitle
- author
- format
- rights
- software
- composer
- arranger
- number-parts
- number-measures
- key-signature
- musical-key
- tempo

Behavior
- No field flags: prints a detailed, multi-section summary, including per-part clefs, key signatures (accidentals), musical key, and tempos.
- One field flag: prints only the raw value (no label). Useful in scripts.
- Multiple field flags: prints selected fields as `Label: value` lines.

Examples
```bash
# Full summary
notare metadata --source score.musicxml

# Single field (bare value)
notare metadata --source score.musicxml --title
notare metadata --source score.musicxml --software
notare metadata --source score.musicxml --key-signature

# Multiple selected (labeled)
notare metadata --source score.musicxml --title --composer --musical-key

# Update metadata and write to a new file (supports piping like other commands)
notare metadata --source score.musicxml --new-title "My new title" --output updated.musicxml
```

### Extract module

```bash
# Extract specific measures and/or parts (supports comma-separated ranges)
notare extract --source score.musicxml --measures 1-4 --part-name Flute,Oboe --output excerpt.musicxml

# Keep all parts but only select specific measures
notare extract --source score.musicxml --measures 1,3,5-8 --output highlights.musicxml

# Combine part number selection with output piping
notare extract --source score.musicxml --part-number 1 --measures 2-4 --output-format musicxml > flute_excerpt.musicxml
```

**NOTES**

- During import we re-number all the measures to start from 1. So the first measure is 1
- If your score has other measures number system it will be overwritten 
- If 0 is passed in measures, it returns the whole score

### Delete module

Remove specific measures and/or parts from a score. After deletions, measures are renumbered to start at 1 and metadata is preserved.

```bash
# Delete measures 2-3 across all parts and write the result
notare delete --source score.musicxml --measures 2-3 --output pruned.musicxml

# Delete a part by name
notare delete --source score.musicxml --part-name Oboe --output no_oboe.musicxml

# Combine deletions and use piping
type tests\data\BrahWiMeSample.musicxml | notare delete --measures 1,3 | notare show
```

**Notes**

- Measure numbering is normalized on import and renumbered after deletions so the final score starts at 1 and counts consecutively.
- Part selection accepts names/ids via `--part-name` and 1-based indices via `--part-number`.
- If you delete all measures, the score will show with a single empty measure
- If you delete all parts, the score will show a single (new) part with a single empty measure

### Analyze module



```bash
# Analyze entire piece or pipeline with extracts
notare analyze --source score.musicxml --key --npvi
notare extract --source score.musicxml --measures 1-4 --output - | notare analyze --key
```

Available analyze flags (combine as needed):
- `--title`
- `--key`
- `--key-clarity`
- `--interval-entropy`
- `--pitch-class-entropy`
- `--npvi`
- `--contour-complexity`
- `--highest-note`
- `--rhythmic-variety`
- `--avg-duration`
- `--number-of-notes`
- `--key-signature`
- `--time-signature`
- `--pitch-range`
- `--articulation-density`
- `--note-density`
- `--avg-tempo`
- `--dynamic-range`
- `--difficulty`
- `--difficulty-categories`

### Show module

```bash
# Render a score in the browser using OpenSheetMusicDisplay
notare show --source score.musicxml

# Hide title/composer/author or part names if desired
notare show --source score.musicxml --hide-title --hide-composer --hide-part-names

# Works in pipelines too (read from stdin if --source omitted). Mac/Linux
cat score.musicxml | notare show --hide-author

# Windows  (note the use of type and the slashes):
type tests\data\BrahWiMeSample.musicxml | notare show

```

If you don't have Lilypond and still want to print/save pdf you can use the browser printing to do it. You just have to set the --print flag and the print dialog is automatically triggered. Note that this is practical but not feasible for batch jobs

```bash
notare show --source score.musicxml --print

type tests\data\BrahWiMeSample.musicxml | notare show --print
```

### Play module

Play a score by rendering it to MIDI and opening your system's default MIDI player. It does not write to stdout.

```bash
# From a file
notare play --source score.musicxml

# Via pipe (macOS/Linux)
cat score.musicxml | notare play

# Windows (note the use of type and backslashes)
type tests\data\BrahWiMeSample.musicxml | notare play
```

Notes:
- Uses music21 to render a temporary `.mid` and opens it with the OS default app.
- Ensure a MIDI-capable player is installed/associated on your system.

### Simplify module

Apply one or more simplification algorithms to reduce ornamental complexity while preserving the musical gist.

```bash
# Remove common ornaments and short neighbors using a heuristic
notare simplify --source score.musicxml --ornament-removal --output simplified.musicxml

# Control the maximum ornament duration threshold relative to the local beat
notare simplify --source score.musicxml --ornament-removal --ornament-removal-duration "1/8" --output simplified.musicxml

# Works with pipes (omit --source to read stdin; omit --output to stream stdout)
type tests\data\BrahWiMeSample.musicxml | notare simplify --ornament-removal > simplified.musicxml
```

Algorithms
- `--ornament-removal`: Simplifies grace notes, turns, trills components, and very short-duration neighbors.

Heuristic (all conditions must hold):
- Duration < X beats (default X = `1/8` of the local beat)
- Stepwise between two longer notes (both neighbors exist and are longer)
- Occurs on a weak beat (music21 `beatStrength` < 0.5)

Duration parameter
- `--ornament-removal-duration "A/B"` sets the threshold as a fraction of the local beat (e.g., `1/8`, `1/4`).
- Beat duration is derived from the current time signature (e.g., quarter in 4/4, dotted quarter in 6/8).


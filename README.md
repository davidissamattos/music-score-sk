# notare

A swiss knife utility for handling music score files in the command line.

The CLI uses [Google's Python Fire](https://github.com/google/python-fire) for the CLI handling, Pytest for tests and behind the scenes most of the calculations and transformations are done with the excelent music21 library

## Installation

Installation from github
```bash
pip install -e .
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

Available metadata flags (--field or --new-field)

* title 
* author 
* format
* composer
* arranger
* number-parts
* number-measures
* key-signature
* tempo

If you add --new-field this means it is expected a new value

```bash
# Inspect metadata (all fields by default, or pick specific fields)
notare metadata --source score.musicxml
notare metadata --source score.musicxml --title --composer

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

# Works in pipelines too (read from stdin if --source omitted)
cat score.musicxml | notare show --hide-author
```

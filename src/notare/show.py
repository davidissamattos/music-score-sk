"""Render scores using OSMD (OpenSheetMusicDisplay)."""

from __future__ import annotations

from pathlib import Path
import tempfile
import webbrowser

from .utils import load_score, write_score

OSMD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
    }}
    #osmd-container {{
      width: 100%;
      height: 100vh;
    }}
  </style>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/opensheetmusicdisplay/1.7.6/opensheetmusicdisplay.min.js"></script>
</head>
<body>
  <div id="osmd-container"></div>
  <script>
    const osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay("osmd-container");
    fetch("{xml_path}")
      .then(response => response.text())
      .then(data => osmd
        .setOptions({{
          drawTitle: {draw_title},
          drawComposer: {draw_composer},
          drawSubtitle: false,
          drawLyricist: {draw_author},
          drawMeasureNumbers: true
        }})
        .then(() => osmd.load(data))
        .then(() => osmd.render())
      );
  </script>
</body>
</html>
"""


def show_score(
    *,
    source: str | None = None,
    hide_title: bool = False,
    hide_author: bool = False,
    hide_composer: bool = False,
    hide_part_names: bool = False,
    stdin_data: bytes | None = None,
) -> str:
    """Render a score using OSMD and open it in the browser."""
    score = load_score(source, stdin_data=stdin_data)

    if hide_part_names:
        for part in score.parts:
            part.partName = ""

    with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False) as xml_file:
        xml_path = Path(xml_file.name)
        score.write("musicxml", fp=str(xml_path))

    page_title = (score.metadata.title if score.metadata else "") or "Score Preview"
    html_content = OSMD_TEMPLATE.format(
        title=page_title,
        xml_path=xml_path.as_uri(),
        draw_title=str(not hide_title).lower(),
        draw_composer=str(not hide_composer).lower(),
        draw_author=str(not hide_author).lower(),
    )

    html_path = Path(tempfile.mkstemp(suffix=".html")[1])
    html_path.write_text(html_content, encoding="utf-8")
    webbrowser.open(html_path.as_uri())
    return f"Opened score preview in browser: {html_path}"

#!/usr/bin/env python3
"""Write the landing page that ties the published pages together.

The module is called ``landing`` rather than ``site`` because ``site`` is a
standard-library module name, and shadowing it from a directory on sys.path
breaks the interpreter in ways that are tedious to diagnose.

    python py/wikidata/main.py site      # docs/index.html

``docs/`` is what GitHub Pages serves. It holds two generated pages -- the
mapping preview and the SPARQL query page -- and the two documents explaining
what is behind them. This step writes the index that links them, so the folder
is a small site rather than a pile of files.
"""

from __future__ import annotations

import argparse
import html
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEFAULT_OUT_DIR = ROOT / "docs"

STYLE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Linux Libertine', Georgia, Times, serif;
       font-size: 15px; line-height: 1.6; color: #202122; background: #f8f9fa;
       padding: 0 20px 60px; }
.wrap { max-width: 820px; margin: 0 auto; background: #fff;
        border: 1px solid #eaecf0; padding: 34px 40px 40px; margin-top: 30px; }
h1 { font-family: 'Linux Libertine', Georgia, serif; font-size: 30px;
     font-weight: normal; }
.lede { color: #54595d; margin-top: 8px; }
h2 { font-family: sans-serif; font-size: 13px; text-transform: uppercase;
     letter-spacing: .05em; color: #54595d; margin: 30px 0 10px;
     border-bottom: 1px solid #eaecf0; padding-bottom: 5px; }
a { color: #3366cc; text-decoration: none; }
a:hover { text-decoration: underline; }
.card { border: 1px solid #eaecf0; padding: 16px 18px; margin-bottom: 10px; }
.card h3 { font-size: 17px; font-weight: normal; font-family: 'Linux Libertine',
           Georgia, serif; }
.card p { color: #54595d; font-size: 14px; margin-top: 5px; }
.missing { color: #a32020; font-size: 13px; font-family: sans-serif; }
code { font-family: ui-monospace, Menlo, monospace; font-size: 12.5px;
       background: #f8f9fa; padding: 1px 4px; }
footer { color: #72777d; font-size: 12.5px; margin-top: 30px;
         border-top: 1px solid #eaecf0; padding-top: 14px; }
"""

PAGES = [
    ("preview.html", "Mapping preview",
     "Every entry in the slice with the statements it would produce, rendered "
     "the way Wikidata displays them, and every problem the mapping raises. "
     "Filter by category, by severity or by issue code. Nothing here has been "
     "written to Wikidata."),
    ("sparql.html", "Live queries",
     "Eight queries against the Wikidata Query Service, run from the browser. "
     "Three of them are worklists rather than reports -- for those, an empty "
     "result is the healthy one."),
    ("MAPPING.md", "The mapping",
     "Which open-archaeo column becomes which Wikidata statement, and why. "
     "Also what the columns contain beyond their face value."),
    ("ENRICHMENT.md", "What the data does not hold",
     "The columns are mined out; the metadata that is still missing lives "
     "behind the URLs they contain. Which source answers which gap."),
]


def render(out_dir: Path) -> str:
    cards = []
    for filename, title, blurb in PAGES:
        exists = (out_dir / filename).is_file()
        missing = ("" if exists else
                   '<p class="missing">Not generated yet.</p>')
        cards.append(
            f'<div class="card"><h3><a href="{filename}">{html.escape(title)}</a>'
            f'</h3><p>{html.escape(blurb)}</p>{missing}</div>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>open-archaeo in Wikidata</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
  <h1>open-archaeo in Wikidata</h1>
  <p class="lede">Working pages for the import of
    <a href="https://open-archaeo.info/">open-archaeo</a> into Wikidata. Every
    imported tool carries two statements -- it is an instance of
    <a href="https://www.wikidata.org/wiki/Q141115627">Q141115627</a> and it is
    maintained by
    <a href="https://www.wikidata.org/wiki/Q141169143">Q141169143</a> -- which
    is what makes the set retrievable as a set.</p>

  <h2>Pages</h2>
  {"".join(cards)}

  <h2>How they are made</h2>
  <p>All four are generated from the repository, not written by hand:</p>
  <p><code>python py/main.py</code> builds the tables,
     <code>python py/wikidata/main.py preview</code> and
     <code>python py/wikidata/main.py sparql</code> build the two pages, and
     <code>python py/wikidata/main.py site</code> writes this index. The
     mapping itself lives in <code>py/wikidata/model.py</code>.</p>

  <footer>Generated {date.today().isoformat()}. Nothing on these pages has been
    written to Wikidata; they show what an import would do and what still
    stands in its way.</footer>
</div>
</body>
</html>
"""


def run(out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(render(out_dir), encoding="utf-8")
    missing = [name for name, _, _ in PAGES if not (out_dir / name).is_file()]
    print(f"{path}", file=sys.stderr)
    if missing:
        print(f"  not generated yet: {', '.join(missing)}", file=sys.stderr)
    return path


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="the published folder (default: docs/)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_arguments(parser)
    run(parser.parse_args(argv).out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

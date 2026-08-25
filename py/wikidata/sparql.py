#!/usr/bin/env python3
"""Build the query page from ``queries.py``.

    python py/wikidata/main.py sparql            # write docs/sparql.html
    python py/wikidata/sparql.py --verify        # also run every query first

Two products from one source::

    queries.py  ->  docs/sparql.html          (interactive, runs in the browser)
                ->  docs/queries/<id>.rq      (plain files, prefixes included)

Unlike the wdt-* query pages, which parse a static Turtle file under Pyodide,
this one talks to a live endpoint: the graph being queried is Wikidata, and
there is no local copy of it. The trade is the usual one -- nothing to
download, but the page needs the service to be up, and a query typed here does
leave the machine.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import queries as query_source

HERE = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = HERE / "docs"

# Pinned deliberately: an unpinned endpoint is not a thing, but an unpinned
# result limit is -- some of these queries are unbounded and an unlimited table
# can hang a phone.
MAX_ROWS = 500
ENDPOINT = "https://query.wikidata.org/sparql"


STYLE = """
:root {
  --ink: #1c1c1c; --muted: #6a6a6a; --line: #e0ddd6; --bg: #fdfcfa;
  --card: #ffffff; --accent: #6d4c2f; --code-bg: #f6f4f0;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0 1.25rem 4rem; background: var(--bg); color: var(--ink);
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
.wrap { max-width: 62rem; margin: 0 auto; }
header { padding: 2.5rem 0 1.5rem; border-bottom: 1px solid var(--line); }
h1 { margin: 0 0 .5rem; font-size: 1.9rem; letter-spacing: -.01em; }
.intro { color: var(--muted); max-width: 46rem; }
nav { margin-top: 1rem; font-size: .9rem; }
nav a { color: var(--accent); margin-right: 1rem; }
.query { border: 1px solid var(--line); background: var(--card);
         border-radius: 6px; padding: 1.25rem; margin: 1.75rem 0; }
.query h2 { margin: 0 0 .35rem; font-size: 1.15rem; }
.query .note { color: var(--muted); font-size: .92rem; margin: 0 0 .9rem;
               max-width: 46rem; }
textarea {
  width: 100%; font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
  padding: .8rem; border: 1px solid var(--line); border-radius: 4px;
  background: var(--code-bg); color: var(--ink); resize: vertical;
}
.controls { margin-top: .7rem; display: flex; gap: .5rem; align-items: center;
            flex-wrap: wrap; }
button {
  font: inherit; font-size: .88rem; padding: .35rem .9rem; cursor: pointer;
  border: 1px solid var(--line); border-radius: 4px; background: #fff;
  color: var(--ink);
}
button.run { background: var(--accent); border-color: var(--accent); color: #fff; }
button:disabled { opacity: .5; cursor: default; }
.status { font-size: .85rem; color: var(--muted); margin-left: .3rem; }
.status.error { color: #9b2c2c; }
.results { margin-top: .9rem; overflow-x: auto; }
table { border-collapse: collapse; font-size: .86rem; width: 100%; }
th, td { text-align: left; padding: .35rem .6rem; border-bottom: 1px solid var(--line);
         vertical-align: top; }
th { font-weight: 600; white-space: nowrap; background: var(--code-bg); }
td.empty { color: #b8b3aa; }
a { color: var(--accent); }
footer { margin-top: 3rem; padding-top: 1.25rem; border-top: 1px solid var(--line);
         color: var(--muted); font-size: .88rem; }
code { background: var(--code-bg); padding: .1em .35em; border-radius: 3px;
       font-size: .9em; }
"""


SCRIPT = """
var ENDPOINT = "__ENDPOINT__";
var MAX_ROWS = __MAX_ROWS__;
var PREFIXES = __PREFIXES__;
var ORIGINAL = __ORIGINAL__;

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function cell(binding) {
  if (!binding) return '<td class="empty">--</td>';
  var value = binding.value;
  if (binding.type === "uri") {
    var label = value.replace("http://www.wikidata.org/entity/", "");
    return '<td><a href="' + escapeHtml(value) + '" target="_blank" rel="noopener">'
      + escapeHtml(label) + "</a></td>";
  }
  return "<td>" + escapeHtml(value) + "</td>";
}

function renderTable(data) {
  var vars = data.head.vars;
  var rows = data.results.bindings;
  if (!rows.length) {
    return '<p class="status">No results. On this page an empty result is '
      + "usually an answer, not a failure -- several queries are worklists "
      + "that empty as the data improves.</p>";
  }
  var shown = rows.slice(0, MAX_ROWS);
  var out = "<table><thead><tr>";
  vars.forEach(function (name) { out += "<th>" + escapeHtml(name) + "</th>"; });
  out += "</tr></thead><tbody>";
  shown.forEach(function (row) {
    out += "<tr>";
    vars.forEach(function (name) { out += cell(row[name]); });
    out += "</tr>";
  });
  out += "</tbody></table>";
  if (rows.length > shown.length) {
    out += '<p class="status">Showing ' + shown.length + " of " + rows.length
      + " rows.</p>";
  }
  return out;
}

function run(id) {
  var box = document.getElementById("q-" + id);
  var status = document.getElementById("s-" + id);
  var results = document.getElementById("r-" + id);
  var button = document.getElementById("b-" + id);
  var query = PREFIXES + "\\n" + box.value;
  var started = Date.now();

  button.disabled = true;
  status.className = "status";
  status.textContent = "running...";
  results.innerHTML = "";

  fetch(ENDPOINT + "?query=" + encodeURIComponent(query), {
    headers: { "Accept": "application/sparql-results+json" }
  }).then(function (response) {
    if (!response.ok) {
      return response.text().then(function (text) {
        throw new Error("HTTP " + response.status + ": " + text.slice(0, 300));
      });
    }
    return response.json();
  }).then(function (data) {
    var seconds = ((Date.now() - started) / 1000).toFixed(1);
    status.textContent = data.results.bindings.length + " rows in " + seconds + " s";
    results.innerHTML = renderTable(data);
  }).catch(function (error) {
    status.className = "status error";
    status.textContent = String(error.message || error);
  }).then(function () {
    button.disabled = false;
  });
}

function reset(id) {
  document.getElementById("q-" + id).value = ORIGINAL[id];
  document.getElementById("s-" + id).textContent = "";
  document.getElementById("r-" + id).innerHTML = "";
}

function openInWdqs(id) {
  var query = PREFIXES + "\\n" + document.getElementById("q-" + id).value;
  window.open("https://query.wikidata.org/#" + encodeURIComponent(query), "_blank");
}

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("textarea").forEach(function (box) {
    box.rows = Math.min(28, box.value.split("\\n").length + 1);
  });
});
"""


def render_page(page: dict, prefixes: str, query_list: list[dict]) -> str:
    """Assemble the single self-contained HTML file."""
    originals = {q["id"]: q["sparql"] for q in query_list}
    script = (SCRIPT
              .replace("__ENDPOINT__", ENDPOINT)
              .replace("__MAX_ROWS__", str(MAX_ROWS))
              .replace("__PREFIXES__", json.dumps(prefixes))
              .replace("__ORIGINAL__", json.dumps(originals)))

    blocks = []
    for query in query_list:
        qid = query["id"]
        blocks.append(f"""
    <section class="query" id="{qid}">
      <h2>{html.escape(query['title'])}</h2>
      <p class="note">{query['intro']}</p>
      <textarea id="q-{qid}" spellcheck="false">{html.escape(query['sparql'])}</textarea>
      <div class="controls">
        <button class="run" id="b-{qid}" onclick="run('{qid}')">Run</button>
        <button onclick="reset('{qid}')">Reset</button>
        <button onclick="openInWdqs('{qid}')">Open in WDQS</button>
        <a href="queries/{qid}.rq" download>.rq</a>
        <span class="status" id="s-{qid}"></span>
      </div>
      <div class="results" id="r-{qid}"></div>
    </section>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(page['title'])}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>{html.escape(page['title'])}</h1>
    <p class="intro">{page['intro']}</p>
    <nav>
      <a href="https://www.wikidata.org/wiki/Wikidata:WikiProject_Informatics/Software/Properties">Software properties</a>
      <a href="MAPPING.md">Mapping</a>
      <a href="https://open-archaeo.info/">open-archaeo</a>
    </nav>
  </header>
{"".join(blocks)}
  <footer>{page['footer']}</footer>
</div>
<script>{script}</script>
</body>
</html>
"""


def verify(prefixes: str, query_list: list[dict]) -> int:
    """Run every query against WDQS; report row counts. Returns the failure count."""
    from api import WikidataError, sparql  # local: verification is optional

    failures = 0
    for query in query_list:
        try:
            rows = sparql(prefixes + "\n" + query["sparql"])
        except WikidataError as error:
            print(f"  FAILED {query['id']}: {error}", file=sys.stderr)
            failures += 1
            continue
        print(f"  {len(rows):5d}  {query['id']}", file=sys.stderr)
    return failures


def run(out_dir: Path = DEFAULT_OUT_DIR, *, do_verify: bool = False,
        strict: bool = False) -> list[Path]:
    """Write the page and the .rq files; return the paths written."""
    query_list = query_source.QUERIES
    prefixes = query_source.PREFIXES.rstrip()

    if do_verify:
        print(f"verifying {len(query_list)} queries against {ENDPOINT}",
              file=sys.stderr)
        failures = verify(prefixes, query_list)
        if failures and strict:
            sys.exit(f"error: {failures} queries failed")

    out_dir.mkdir(parents=True, exist_ok=True)
    query_dir = out_dir / "queries"
    query_dir.mkdir(exist_ok=True)

    written = []
    for query in query_list:
        path = query_dir / f"{query['id']}.rq"
        path.write_text(f"# {query['title']}\n{prefixes}\n\n{query['sparql']}\n",
                        encoding="utf-8")
        written.append(path)

    page = out_dir / "sparql.html"
    page.write_text(render_page(query_source.PAGE, prefixes, query_list),
                    encoding="utf-8")
    written.insert(0, page)

    print(f"{len(query_list)} queries -> {page} and {query_dir}/", file=sys.stderr)
    return written


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="where to write the page (default: py/docs/)")
    parser.add_argument("--verify", action="store_true",
                        help="run every query against WDQS before writing")
    parser.add_argument("--strict", action="store_true",
                        help="with --verify, fail the build on a failing query")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_arguments(parser)
    args = parser.parse_args(argv)
    run(args.out_dir, do_verify=args.verify, strict=args.strict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

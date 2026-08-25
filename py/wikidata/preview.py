#!/usr/bin/env python3
"""Show what would land in Wikidata, as a page that looks like Wikidata.

    python py/wikidata/main.py preview        # write docs/preview.html

The dry run of ``push`` prints statements as text, which is fine for checking a
single row and hopeless for judging whether the *modelling* is right. This
renders the same statements the way Wikidata would display them -- property
label and number on the left, value on the right, qualifiers indented -- so a
reviewer can look at an item and say "that is not what a repository statement
should look like" without reading Python.

Nothing here contacts Wikidata unless ``--labels`` is given, and even then it
only reads. It never writes anything anywhere except the HTML file.

The sample is chosen rather than taken from the top: every category appears,
and so does every case that is modelled differently -- a CRAN package, a Zenodo
DOI, a host application instead of a language, an entry with no repository at
all. Those are the rows where a mapping error shows up.
"""

from __future__ import annotations

import argparse
import csv
import html
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from model import (
    CHUBLET_CLASS, CHUBLET_WIKIPROJECT, FORMATTER_URLS, ISSUE_LEGEND,
    MODELLING_NOTES, PROPERTY_LABELS, Issue, build_claims,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
# Repo-root docs/, so GitHub Pages can serve it. See docs/index.html.
DEFAULT_OUTPUT = ROOT / "docs" / "preview.html"

WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/{}"
WIKIDATA_PROPERTY = "https://www.wikidata.org/wiki/Property:{}"


# --------------------------------------------------------------------------
# Choosing the sample
# --------------------------------------------------------------------------

# Each test names a case that is modelled differently from the others. The
# sample takes one row for each, so a mapping mistake has somewhere to show.
FEATURES = {
    "Packages and libraries": lambda r: r["category"] == "Packages and libraries",
    "Standalone software": lambda r: r["category"] == "Standalone software",
    "Scripts": lambda r: r["category"] == "Scripts",
    "CRAN package": lambda r: r["registry_name"] == "CRAN",
    "PyPI package": lambda r: r["registry_name"] == "PyPI",
    "Zenodo deposit DOI": lambda r: r["doi"].startswith("10.5281/"),
    "publisher DOI": lambda r: bool(r["doi"]) and not r["doi"].startswith("10.5281/"),
    "archived snapshot": lambda r: bool(r["internetarchive"]),
    "no archived snapshot": lambda r: bool(r["repository"]) and not r["internetarchive"],
    "host application": lambda r: r["platform_role"] == "host application",
    "language given": lambda r: r["platform_role"] == "language",
    "no platform": lambda r: not r["platform"],
    "no repository": lambda r: not r["repository"],
    "several repositories": lambda r: "|" in r["repository"],
    "Codeberg": lambda r: "Codeberg" in r["repository_host"],
    "Bitbucket": lambda r: "Bitbucket" in r["repository_host"],
    "Gist": lambda r: "Gist" in r["repository_host"],
    "GitLab": lambda r: "GitLab" in r["repository_host"],
    "with publication": lambda r: bool(r["publication"]),
    "with website": lambda r: bool(r["website"]),
    "several authors": lambda r: "|" in r["authors"],
}


def cases_for(row: dict) -> list[str]:
    """Every modelling case this row is an example of."""
    return [name for name, test in FEATURES.items() if test(row)]


def choose_sample(rows: list[dict], size: int = 0) -> list[dict]:
    """The rows to render, in name order.

    ``size`` of 0 means all of them, which is the default: the page is a test
    of the mapping, and a mapping is tested against the whole dataset rather
    than against a sample of it. A positive ``size`` keeps one row per
    modelling case first, then fills up -- useful for a quick look.
    """
    ordered = sorted(rows, key=lambda r: r["id"])
    if not size or size >= len(ordered):
        return sorted(rows, key=lambda r: r["name"].lower())
    ordered = sorted(rows, key=lambda r: r["id"])
    picked: dict[str, list[str]] = {}
    for name, test in FEATURES.items():
        for row in ordered:
            if test(row):
                if row["id"] in picked:
                    picked[row["id"]].append(name)
                else:
                    picked[row["id"]] = [name]
                break

    if len(picked) < size:
        # Fill from the categories in turn, so the padding stays balanced
        # rather than adding twenty more R packages.
        by_category: dict[str, list[dict]] = {}
        for row in ordered:
            by_category.setdefault(row["category"], []).append(row)
        categories = sorted(by_category)
        index = 0
        while len(picked) < size and any(by_category.values()):
            bucket = by_category[categories[index % len(categories)]]
            index += 1
            while bucket:
                row = bucket.pop(0)
                if row["id"] not in picked:
                    picked[row["id"]] = []
                    break

    by_id = {row["id"]: row for row in ordered}
    chosen = [by_id[i] for i in list(picked)[:size]]
    return sorted(chosen, key=lambda r: r["name"].lower())


# --------------------------------------------------------------------------
# Labels
# --------------------------------------------------------------------------

def collect_item_values(plans: list) -> set[str]:
    """Every Q-id appearing as a value or qualifier value on the page."""
    found = {CHUBLET_CLASS, CHUBLET_WIKIPROJECT}
    for _, claims, _ in plans:
        for claim in claims:
            if claim.datatype == "item":
                found.add(claim.value)
            for qualifier in claim.qualifiers:
                if qualifier.datatype == "item":
                    found.add(qualifier.value)
    return found


def fetch_labels(qids: set[str]) -> dict[str, str]:
    """Read English labels for the Q-ids used. Read-only, and optional."""
    from api import WikidataError, get_entities

    try:
        entities = get_entities(sorted(qids), props="labels")
    except WikidataError as error:
        print(f"  could not read labels ({error}); showing Q-ids only",
              file=sys.stderr)
        return {}
    return {qid: entity.get("labels", {}).get("en", {}).get("value", "")
            for qid, entity in entities.items() if "id" in entity}


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

STYLE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Linux Libertine', Georgia, Times, serif;
       font-size: 14px; color: #202122; background: #f8f9fa; padding-bottom: 60px; }
.page { max-width: 900px; margin: 0 auto 26px; background: #fff;
        padding: 20px 30px 26px; border: 1px solid #eaecf0; }
.intro { max-width: 900px; margin: 26px auto; background: #fff;
         padding: 22px 30px 26px; border: 1px solid #eaecf0; }
.intro h1 { font-family: 'Linux Libertine', Georgia, serif; font-size: 26px;
            font-weight: normal; }
.intro h2 { font-family: sans-serif; font-size: 13px; text-transform: uppercase;
            letter-spacing: .05em; color: #54595d; margin: 20px 0 8px; }
.intro p { margin-top: 10px; line-height: 1.55; }
code { font-family: ui-monospace, Menlo, monospace; font-size: 12.5px;
       background: #f8f9fa; padding: 1px 4px; }
.tally { display: flex; gap: 26px; flex-wrap: wrap; margin-top: 16px;
         padding-top: 14px; border-top: 1px solid #eaecf0; }
.tally div { font-family: sans-serif; font-size: 12px; color: #54595d; }
.tally strong { display: block; font-size: 22px; color: #202122;
                font-family: 'Linux Libertine', Georgia, serif; font-weight: normal; }
.legend { width: 100%; border-collapse: collapse; font-size: 12.5px;
          margin-top: 6px; }
.legend th { text-align: left; font-family: sans-serif; font-size: 11px;
             text-transform: uppercase; color: #72777d; padding: 4px 8px;
             border-bottom: 1px solid #eaecf0; }
.legend td { padding: 6px 8px; border-bottom: 1px solid #eaecf0;
             vertical-align: top; }
.legend tr { cursor: pointer; }
.legend tr:hover td { background: #f8f9fa; }
.legend .count { text-align: right; font-family: sans-serif; white-space: nowrap; }
.legend code { background: none; padding: 0; }
.controls { position: sticky; top: 0; z-index: 5; background: #fff;
            border: 1px solid #eaecf0; border-top: none; max-width: 900px;
            margin: -26px auto 26px; padding: 12px 30px; display: flex;
            gap: 10px; align-items: center; flex-wrap: wrap;
            font-family: sans-serif; font-size: 12.5px; }
.controls label { color: #54595d; }
.controls select, .controls input {
  font: inherit; padding: 4px 6px; border: 1px solid #a2a9b1; border-radius: 2px;
  background: #fff; color: #202122; }
.controls input { min-width: 190px; }
.controls button { font: inherit; padding: 4px 10px; border: 1px solid #a2a9b1;
                   background: #f8f9fa; border-radius: 2px; cursor: pointer; }
#result-count { color: #54595d; margin-left: auto; }
.item-header { border-bottom: 1px solid #a2a9b1; padding-bottom: 8px;
               margin-bottom: 16px; }
.item-title { font-family: 'Linux Libertine', Georgia, serif; font-size: 28px;
              font-weight: normal; color: #000; line-height: 1.2; }
.item-id { font-size: 13px; color: #555; margin-top: 2px; }
.section-heading { font-family: sans-serif; font-size: 18px; font-weight: bold;
                   border-bottom: 1px solid #a2a9b1; padding-bottom: 4px;
                   margin: 20px 0 12px; }
.statement-group { border: 1px solid #eaecf0; border-radius: 2px;
                   margin-bottom: 8px; overflow: hidden; }
.statement-row { display: grid; grid-template-columns: 200px 1fr;
                 border-bottom: 1px solid #eaecf0; }
.statement-row:last-child { border-bottom: none; }
.prop-cell { background: #f8f9fa; padding: 8px 10px;
             border-right: 1px solid #eaecf0; font-size: 13px; }
.prop-link { color: #3366cc; text-decoration: none; }
.prop-link:hover { text-decoration: underline; }
.prop-id { display: inline; color: #72777d; font-size: 11px; margin-left: 4px; }
.value-cell { padding: 8px 10px; background: #fff; }
.main-value { color: #3366cc; font-size: 13.5px; word-break: break-all; }
.main-value.literal { color: #202122; }
a.main-value, a { color: #3366cc; text-decoration: none; }
a:hover { text-decoration: underline; }
.qualifiers { margin-top: 6px; padding-left: 12px; border-left: 3px solid #eaecf0; }
.qualifier-row { display: grid; grid-template-columns: 185px 1fr; gap: 4px;
                 margin-bottom: 3px; font-size: 12.5px; align-items: start; }
.qual-prop { color: #3366cc; font-size: 12px; }
.qual-prop span { display: inline; color: #72777d; font-size: 10.5px;
                  margin-left: 3px; }
.qual-value { color: #202122; word-break: break-all; }
.qual-value.item-val { color: #3366cc; }
.q-id { color: #72777d; font-size: 11px; margin-left: 4px; }
.badge { display: inline-block; font-size: 10px; padding: 1px 5px;
         border-radius: 2px; margin-left: 5px; vertical-align: middle;
         font-family: sans-serif; }
.badge-obligatory { background: #cce5ff; color: #004085; }
.badge-derived { background: #e2e3f3; color: #3b3d6b; }
.badge-matched { background: #d4edda; color: #155724; }
.badge-unmatched { background: #f8d7da; color: #721c24; }
.badge-case { background: #eaecf0; color: #54595d; margin: 0 4px 4px 0; }
.terms { border: 1px solid #eaecf0; margin-bottom: 8px; }
.term-row { display: grid; grid-template-columns: 200px 1fr;
            border-bottom: 1px solid #eaecf0; }
.term-row:last-child { border-bottom: none; }
.term-label { background: #f8f9fa; padding: 8px 10px; font-size: 13px;
              border-right: 1px solid #eaecf0; }
.term-value { padding: 8px 10px; }
.note { font-family: sans-serif; font-size: 11.5px; color: #72777d;
        margin-top: 4px; }
.issues { border-radius: 2px; padding: 11px 13px; margin-top: 10px; }
.issues h3 { font-family: sans-serif; font-size: 11.5px; text-transform: uppercase;
             letter-spacing: .04em; margin-bottom: 7px; }
.issues li { font-size: 12.5px; margin-left: 16px; margin-bottom: 5px;
             line-height: 1.45; }
.issues .code { font-family: ui-monospace, Menlo, monospace; font-size: 11px;
                padding: 1px 4px; border-radius: 2px; margin-right: 5px; }
.issues .detail { color: #54595d; word-break: break-all; }
.blocked { border: 1px solid #e6a2a2; background: #fdf3f3; }
.blocked h3 { color: #a32020; }
.blocked .code { background: #f8d7da; color: #721c24; }
.deferred { border: 1px solid #f0d8a8; background: #fffaf0; }
.deferred h3 { color: #856404; }
.deferred .code { background: #fff3cd; color: #856404; }
.notes { border: 1px solid #eaecf0; background: #fafafa; }
.notes h3 { color: #54595d; }
.notes .code { background: #eaecf0; color: #54595d; }
.command { font-family: ui-monospace, Menlo, monospace; font-size: 12px;
           background: #f8f9fa; border: 1px solid #eaecf0; padding: 7px 9px;
           margin-top: 14px; color: #54595d; word-break: break-all; }
.cases { margin-top: 8px; }
.hidden { display: none; }
"""


def _entity(qid: str, labels: dict[str, str]) -> str:
    label = labels.get(qid, "")
    text = html.escape(label) if label else html.escape(qid)
    tail = f'<span class="q-id">{html.escape(qid)}</span>' if label else ""
    return f'<a href="{WIKIDATA_ENTITY.format(qid)}" target="_blank">{text}</a>{tail}'


def _value(claim, labels: dict[str, str], *, qualifier: bool = False) -> str:
    css = "qual-value" if qualifier else "main-value"
    if claim.datatype == "item":
        return f'<span class="{css} item-val">{_entity(claim.value, labels)}</span>'
    if claim.datatype == "url":
        safe = html.escape(claim.value)
        return f'<a class="{css}" href="{safe}" target="_blank">{safe}</a>'
    if claim.prop in FORMATTER_URLS:
        target = FORMATTER_URLS[claim.prop].format(claim.value)
        return (f'<a class="{css}" href="{html.escape(target)}" target="_blank">'
                f'{html.escape(claim.value)}</a>')
    if claim.datatype.startswith("monolingual"):
        _, _, language = claim.datatype.partition("@")
        return (f'<span class="{css} literal">{html.escape(claim.value)}'
                f'<span class="q-id">{html.escape(language or "en")}</span></span>')
    return f'<span class="{css} literal">{html.escape(str(claim.value))}</span>'


def _property(pid: str, *, qualifier: bool = False) -> str:
    label = PROPERTY_LABELS.get(pid, pid)
    css = "qual-prop" if qualifier else "prop-link"
    return (f'<a class="{css}" href="{WIKIDATA_PROPERTY.format(pid)}" '
            f'target="_blank">{html.escape(label)}</a>'
            f'<span class="prop-id">{pid}</span>')


def render_claim(claim, labels: dict[str, str]) -> str:
    badge = ""
    if claim.note.startswith("obligatory"):
        badge = '<span class="badge badge-obligatory">on every item</span>'
    elif claim.note:
        badge = (f'<span class="badge badge-derived">'
                 f'{html.escape(claim.note)}</span>')

    qualifiers = ""
    if claim.qualifiers:
        rows = "".join(
            f'<div class="qualifier-row">'
            f'<div class="qual-prop">{_property(q.prop, qualifier=True)}</div>'
            f'<div>{_value(q, labels, qualifier=True)}</div></div>'
            for q in claim.qualifiers)
        qualifiers = f'<div class="qualifiers">{rows}</div>'

    return (f'<div class="statement-row">'
            f'<div class="prop-cell">{_property(claim.prop)}</div>'
            f'<div class="value-cell">{_value(claim, labels)}{badge}'
            f'{qualifiers}</div></div>')


ISSUE_BLOCKS = (
    (Issue.BLOCKED, "blocked", "Blocked -- would be wrong or invalid"),
    (Issue.DEFERRED, "deferred", "Deferred -- a value exists, but not here"),
    (Issue.NOTE, "notes", "Notes"),
)


def render_issues(issues: list) -> str:
    """Three boxes, one per severity, each explaining itself."""
    out = []
    for severity, css, title in ISSUE_BLOCKS:
        group = [i for i in issues if i.severity == severity]
        if not group:
            continue
        items = "".join(
            f'<li><span class="code">{html.escape(i.code)}</span>'
            f'{html.escape(i.message)}'
            + (f'<div class="detail">{html.escape(i.detail)}</div>'
               if i.detail else "")
            + "</li>"
            for i in group)
        out.append(f'<div class="issues {css}"><h3>{title} ({len(group)})</h3>'
                   f'<ul>{items}</ul></div>')
    return "".join(out)


def render_item(row: dict, claims: list, issues: list,
                labels: dict[str, str]) -> str:
    qid = row.get("qid", "")
    if qid:
        head = (f'Item: <a href="{WIKIDATA_ENTITY.format(qid)}" target="_blank">'
                f'{html.escape(qid)}</a>'
                f'<span class="badge badge-matched">reconciled</span>')
    else:
        head = ('Item: not reconciled'
                '<span class="badge badge-unmatched">push would skip this</span>')

    cases = cases_for(row)
    chips = ""
    if cases:
        chips = ('<div class="cases">'
                 + "".join(f'<span class="badge badge-case">{html.escape(c)}</span>'
                           for c in cases) + "</div>")

    grouped: dict[str, list] = {}
    for claim in claims:
        grouped.setdefault(claim.prop, []).append(claim)
    groups = "".join(
        '<div class="statement-group">'
        + "".join(render_claim(c, labels) for c in group)
        + "</div>"
        for group in grouped.values())

    if qid:
        command = (f'<div class="command">python py/wikidata/main.py push '
                   f'--only {html.escape(row["id"])} --live</div>')
    else:
        command = ('<div class="note">No Q-id, so <code>push</code> would skip '
                   'this item. Reconcile it first, or add a Q-id to the '
                   'concordance by hand.</div>')

    codes = " ".join(sorted({i.code for i in issues}))
    severities = " ".join(sorted({i.severity for i in issues})) or "clean"
    haystack = f"{row['name']} {row['id']} {row['description']}".lower()

    return f"""
<div class="page" data-category="{html.escape(row['category'])}"
     data-role="{html.escape(row['platform_role'] or 'none')}"
     data-codes="{html.escape(codes)}"
     data-severities="{html.escape(severities)}"
     data-reconciled="{'yes' if qid else 'no'}"
     data-search="{html.escape(haystack)}">
  <div class="item-header">
    <h1 class="item-title">{html.escape(row['name'])}</h1>
    <div class="item-id">{head} &middot; open-archaeo
      <a href="{html.escape(row['url'])}" target="_blank">{html.escape(row['id'])}</a>
      &middot; {html.escape(row['category'])}</div>
    {chips}
  </div>

  <div class="section-heading">Terms</div>
  <div class="terms">
    <div class="term-row"><div class="term-label">Label (en)</div>
      <div class="term-value">{html.escape(row['name'])}</div></div>
    <div class="term-row"><div class="term-label">Description (en)</div>
      <div class="term-value">{html.escape(row['description'])}</div></div>
  </div>

  <div class="section-heading">Statements</div>
  {groups}
  {render_issues(issues)}
  {command}
</div>"""


SCRIPT = """
var items = Array.prototype.slice.call(document.querySelectorAll('.page'));
var counter = document.getElementById('result-count');

function currentFilters() {
  return {
    category: document.getElementById('f-category').value,
    problem: document.getElementById('f-problem').value,
    code: document.getElementById('f-code').value,
    text: document.getElementById('f-text').value.trim().toLowerCase()
  };
}

function matches(el, f) {
  if (f.category && el.dataset.category !== f.category) return false;
  if (f.code && el.dataset.codes.split(' ').indexOf(f.code) === -1) return false;
  if (f.text && el.dataset.search.indexOf(f.text) === -1) return false;
  var sev = el.dataset.severities.split(' ');
  if (f.problem === 'blocked' && sev.indexOf('blocked') === -1) return false;
  if (f.problem === 'deferred' && sev.indexOf('deferred') === -1) return false;
  if (f.problem === 'any' && el.dataset.severities === 'clean') return false;
  if (f.problem === 'clean' && el.dataset.severities !== 'clean') return false;
  if (f.problem === 'reconciled' && el.dataset.reconciled !== 'yes') return false;
  if (f.problem === 'unreconciled' && el.dataset.reconciled !== 'no') return false;
  return true;
}

function apply() {
  var f = currentFilters(), shown = 0;
  items.forEach(function (el) {
    var ok = matches(el, f);
    el.classList.toggle('hidden', !ok);
    if (ok) shown++;
  });
  counter.textContent = shown + ' of ' + items.length + ' items';
}

function filterByCode(code) {
  document.getElementById('f-code').value = code;
  document.getElementById('f-problem').value = '';
  apply();
  window.scrollTo(0, document.querySelector('.controls').offsetTop);
}

function resetFilters() {
  document.getElementById('f-category').value = '';
  document.getElementById('f-problem').value = '';
  document.getElementById('f-code').value = '';
  document.getElementById('f-text').value = '';
  apply();
}

document.addEventListener('DOMContentLoaded', function () {
  ['f-category', 'f-problem', 'f-code'].forEach(function (id) {
    document.getElementById(id).addEventListener('change', apply);
  });
  document.getElementById('f-text').addEventListener('input', apply);
  apply();
});
"""


def render(plans: list, labels: dict[str, str], *, slice_path: str,
           total_rows: int, resolved: int, vocabulary_open: int) -> str:
    statements = sum(len(claims) for _, claims, _ in plans)
    qualifiers = sum(len(c.qualifiers) for _, claims, _ in plans for c in claims)
    matched = sum(1 for row, _, _ in plans if row.get("qid"))

    by_code = Counter(issue.code for _, _, issues in plans for issue in issues)
    items_by_code = Counter(code for _, _, issues in plans
                            for code in {i.code for i in issues})
    blocked_items = sum(1 for _, _, issues in plans
                        if any(i.severity == Issue.BLOCKED for i in issues))
    clean_items = sum(1 for _, _, issues in plans if not issues)

    legend_rows = "".join(
        f'<tr onclick="filterByCode(\'{code}\')">'
        f'<td><code>{html.escape(code)}</code></td>'
        f'<td><span class="badge badge-case">{severity}</span></td>'
        f'<td>{html.escape(message)}</td>'
        f'<td class="count">{items_by_code.get(code, 0)} items<br>'
        f'<span class="note">{by_code.get(code, 0)} times</span></td></tr>'
        for code, (severity, message) in ISSUE_LEGEND.items()
        if by_code.get(code))

    categories = sorted({row["category"] for row, _, _ in plans})
    category_options = "".join(
        f'<option value="{html.escape(c)}">{html.escape(c)}</option>'
        for c in categories)
    code_options = "".join(
        f'<option value="{html.escape(c)}">{html.escape(c)} '
        f'({items_by_code[c]})</option>'
        for c in sorted(items_by_code))

    ready = [row["id"] for row, _, issues in plans
             if row.get("qid") and not any(i.severity == Issue.BLOCKED
                                           for i in issues)][:3]
    if ready:
        only = " ".join(f"--only {i}" for i in ready)
        next_step = (f'<p>Three items that are reconciled and carry nothing '
                     f'blocked:</p><div class="command">python '
                     f'py/wikidata/main.py push {only} --live</div>')
    elif matched:
        next_step = ('<p>Items are reconciled, but every one of them has a '
                     'blocked issue. Clear those first -- the red boxes say '
                     'what each needs.</p>')
    else:
        next_step = ('<p>Nothing is reconciled yet, so <code>push</code> would '
                     'write nothing. Run <code>python py/wikidata/main.py '
                     'reconcile</code>, then regenerate this page.</p>')

    items = "".join(render_item(row, claims, issues, labels)
                    for row, claims, issues in plans)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mapping test: open-archaeo in Wikidata</title>
<style>{STYLE}</style>
</head>
<body>

<div class="intro">
  <h1>What would be written to Wikidata</h1>
  <p>All {len(plans)} entries of <code>{html.escape(slice_path)}</code>,
     rendered the way Wikidata displays statements. Nothing here has been
     written; this is what <code>push --live</code> would send. It is a test of
     the mapping, so it shows the whole set rather than a sample -- use the
     filters to get to the interesting part.</p>

  <h2>What the three boxes under an item mean</h2>
  <p><strong>Blocked</strong>, in red, means the import would produce something
     <em>wrong or invalid</em>: a statement that violates a required-qualifier
     constraint, or an item that cannot be written at all. These are gaps to
     close before writing.</p>
  <p><strong>Deferred</strong>, in amber, means a value exists in open-archaeo
     and is deliberately not written here -- either because it belongs on a
     different statement, or because the Q-id it needs has not been chosen yet.
     Nothing is wrong; something is waiting.</p>
  <p><strong>Notes</strong>, in grey, are remarks about modelling that a
     reviewer should see once and then move on from.</p>

  <h2>Two modelling decisions worth knowing about</h2>
  {"".join(f"<p><strong>{html.escape(title)}.</strong> {html.escape(body)}</p>"
           for title, body in MODELLING_NOTES)}

  <h2>Issues in this run</h2>
  <table class="legend">
    <tr><th>Code</th><th>Severity</th><th>What it means</th><th>How often</th></tr>
    {legend_rows or '<tr><td colspan="4">No issues at all.</td></tr>'}
  </table>
  <p class="note">Click a row to filter the page down to those items.</p>

  <div class="tally">
    <div><strong>{len(plans)}</strong>items</div>
    <div><strong>{matched}</strong>reconciled</div>
    <div><strong>{statements}</strong>statements</div>
    <div><strong>{qualifiers}</strong>qualifiers</div>
    <div><strong>{blocked_items}</strong>with blocked issues</div>
    <div><strong>{clean_items}</strong>with none at all</div>
    <div><strong>{resolved}</strong>vocabulary resolved</div>
    <div><strong>{vocabulary_open}</strong>vocabulary open</div>
  </div>
  {next_step}
  <p class="note">Generated {date.today().isoformat()} &middot; regenerate with
     <code>python py/wikidata/main.py preview</code></p>
</div>

<div class="controls">
  <label for="f-category">Category</label>
  <select id="f-category"><option value="">all</option>{category_options}</select>
  <label for="f-problem">Show</label>
  <select id="f-problem">
    <option value="">all items</option>
    <option value="any">with any issue</option>
    <option value="blocked">with blocked issues</option>
    <option value="deferred">with deferred issues</option>
    <option value="clean">with no issues</option>
    <option value="reconciled">reconciled</option>
    <option value="unreconciled">not reconciled</option>
  </select>
  <label for="f-code">Issue</label>
  <select id="f-code"><option value="">any</option>{code_options}</select>
  <input id="f-text" type="search" placeholder="name, id or description">
  <button onclick="resetFilters()">Reset</button>
  <span id="result-count"></span>
</div>

{items}

<script>{SCRIPT}</script>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Step
# --------------------------------------------------------------------------

def load_slice(path: Path) -> list[dict]:
    if not path.is_file():
        sys.exit(f"error: {path} not found. Run 'python py/main.py' first.")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def merge_qids(rows: list[dict], concordance: Path) -> int:
    """Copy Q-ids from the concordance onto the slice rows, if one exists."""
    if not concordance.is_file():
        for row in rows:
            row.setdefault("qid", "")
        return 0
    with concordance.open(newline="", encoding="utf-8") as handle:
        known = {r["id"]: r.get("qid", "") for r in csv.DictReader(handle)}
    matched = 0
    for row in rows:
        row["qid"] = known.get(row["id"], "")
        matched += bool(row["qid"])
    return matched


def run(*, slice_path: Path, vocabulary: dict, concordance: Path,
        output: Path = DEFAULT_OUTPUT, size: int = 0,
        with_labels: bool = False) -> Path:
    rows = load_slice(slice_path)
    merge_qids(rows, concordance)

    plans = []
    for row in choose_sample(rows, size):
        claims, issues = build_claims(row, vocabulary)
        if not row.get("qid"):
            severity, message = ISSUE_LEGEND["not-reconciled"]
            issues.insert(0, Issue("not-reconciled", severity, message))
        plans.append((row, claims, issues))

    labels: dict[str, str] = {}
    if with_labels:
        print("  reading labels from Wikidata", file=sys.stderr)
        labels = fetch_labels(collect_item_values(plans))

    sections = [s for s in vocabulary if not s.startswith("_")]
    values = [v for s in sections for v in vocabulary[s].values()]
    resolved = sum(1 for v in values if v)

    try:
        relative = slice_path.relative_to(Path.cwd())
    except ValueError:
        relative = slice_path

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(plans, labels, slice_path=str(relative),
                             total_rows=len(rows), resolved=resolved,
                             vocabulary_open=len(values) - resolved),
                      encoding="utf-8")

    by_severity = Counter(i.severity for _, _, issues in plans for i in issues)
    print(f"{len(plans)} items, "
          f"{sum(len(c) for _, c, _ in plans)} statements, "
          f"{by_severity[Issue.BLOCKED]} blocked / "
          f"{by_severity[Issue.DEFERRED]} deferred / "
          f"{by_severity[Issue.NOTE]} notes -> {output}", file=sys.stderr)
    return output


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT,
                        help="where to write the page "
                             "(default: docs/preview.html)")
    parser.add_argument("--size", type=int, default=0, metavar="N",
                        help="show only N items, one per modelling case first "
                             "(default: 0, meaning all of them)")
    parser.add_argument("--labels", action="store_true",
                        help="read English labels for the Q-ids used, so values "
                             "read as words rather than numbers. Read-only")

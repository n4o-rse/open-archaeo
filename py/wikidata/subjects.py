#!/usr/bin/env python3
"""Turn the open-archaeo tags into a subject vocabulary.

    python py/wikidata/main.py subjects            # write the worksheet
    python py/wikidata/main.py subjects --suggest  # with Wikidata candidates
    python py/wikidata/main.py subjects --apply    # read it back into vocabulary.json

``P921`` main subject is the largest single block of unresolved values in the
import -- 56 terms, appearing on every one of the 416 entries -- and it is the
one place where the reconciliation cannot be derived from a URL. It has to be
decided term by term.

What makes that tractable is a file already in the repository and not used by
anything else: ``tags.md`` carries a **scope note** for 58 of the 59 tags. A
one-line definition is the difference between matching *Seriation* to the right
Wikidata item and matching it to the wrong one, so the worksheet carries the
note beside every term.

The worksheet is the handover format between the two hackathon teams: whoever
reconciles fills the ``qid`` column, ``--apply`` reads it back, and both halves
end up using the same items.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEFAULT_TAGS_MD = ROOT / "tags.md"
DEFAULT_OUTPUT = ROOT / "out" / "tag-reconciliation.csv"

COLUMNS = [
    "tag", "kind", "uses_software", "uses_all", "scope_note",
    "examples", "search_term", "qid", "qid_label", "note",
]

# Tags that name what a thing *is* rather than what it is about. A subject
# statement is the wrong home for them: they belong on P31, or nowhere.
FORM_TAGS = {
    "Datasets", "Templates", "Platforms and publications",
    "Educational resources and practical guides",
}

# Catch-alls. "Bits and bobs" is open-archaeo's own word for miscellaneous, and
# it sits on 17 entries in the software subset -- importing it as a subject
# would assert that seventeen tools are about miscellany.
CATCH_ALL_TAGS = {"Bits and bobs", "Lists"}

# Where the obvious search term differs from the tag itself.
SEARCH_OVERRIDES = {
    "Radiocarbon dating, calibration and sequencing": "radiocarbon dating",
    "API interfaces and web scrapers": "web scraping",
    "Literary analysis and epigraphy": "epigraphy",
    "Diagrams and visualizations": "data visualization",
    "Schemas and ontologies": "ontology",
    "Drivers and IO": "device driver",
    "Aerial and satellite imagery": "aerial photography",
    "Instrumental Neutron activation analysis": "neutron activation analysis",
    "X-Ray Fluorescence": "X-ray fluorescence",
    "Harris matrix": "Harris matrix",
    "Harrix matrix": "Harris matrix",
    "Bits and bobs": "",
    "Lists": "",
}


def parse_tag_notes(path: Path = DEFAULT_TAGS_MD) -> dict[str, str]:
    """Read the ``|Tag|Scope|`` table out of tags.md.

    The file is a hand-kept Markdown table and not perfectly regular -- the
    header pipe is missing on one row -- so the parser is deliberately loose:
    two cells, second one non-empty and not a separator.
    """
    if not path.is_file():
        print(f"  no {path}, continuing without scope notes", file=sys.stderr)
        return {}
    notes: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 2:
            continue
        tag, note = cells
        if not tag or not note or note.startswith((":", "-")) or note == "Scope":
            continue
        notes[tag] = note
    return notes


def collect_tags(rows: list[dict]) -> Counter:
    return Counter(tag for row in rows
                   for tag in row["tags"].split("|") if tag)


def kind_of(tag: str) -> str:
    if tag in CATCH_ALL_TAGS:
        return "catch-all"
    if tag in FORM_TAGS:
        return "form"
    return "subject"


def search_term(tag: str) -> str:
    if tag in SEARCH_OVERRIDES:
        return SEARCH_OVERRIDES[tag]
    return tag.lower()


def build_worksheet(software: Counter, everything: Counter,
                    notes: dict[str, str], examples: dict[str, list[str]],
                    previous: dict[str, dict] | None = None) -> list[dict]:
    """One row per tag, richest first. Existing decisions are carried over."""
    previous = previous or {}
    rows = []
    for tag, count in software.most_common():
        old = previous.get(tag, {})
        note = ""
        if tag not in notes:
            note = ("no scope note in tags.md -- tags.md spells it "
                    "'Harrix matrix', which is a typo worth reporting upstream"
                    if tag == "Harris matrix" else "no scope note in tags.md")
        if tag == "Harrix matrix":
            note = "misspelling of 'Harris matrix'; one entry. Fix upstream."
        rows.append({
            "tag": tag,
            "kind": old.get("kind") or kind_of(tag),
            "uses_software": count,
            "uses_all": everything.get(tag, count),
            "scope_note": notes.get(tag, ""),
            "examples": "; ".join(examples.get(tag, [])[:3]),
            "search_term": old.get("search_term") or search_term(tag),
            "qid": old.get("qid", ""),
            "qid_label": old.get("qid_label", ""),
            "note": old.get("note") or note,
        })
    return rows


def add_candidates(rows: list[dict], limit: int = 3) -> None:
    """Fill qid_label with Wikidata search hits, never the qid itself.

    Same principle as ``vocab --suggest``: a search is a good way to find a
    candidate and a bad way to choose one, so the column that decides stays
    empty until a person fills it.
    """
    from api import WikidataError, search_entities

    for row in rows:
        if row["qid"] or not row["search_term"]:
            continue
        try:
            hits = search_entities(row["search_term"], limit=limit)
        except WikidataError as error:
            print(f"  search failed for {row['tag']}: {error}", file=sys.stderr)
            continue
        row["qid_label"] = " | ".join(
            f"{h['id']} {h.get('label', '')}"
            + (f" ({h['description']})" if h.get("description") else "")
            for h in hits) or "(no hits)"


def read_worksheet(path: Path) -> list[dict]:
    if not path.is_file():
        sys.exit(f"error: no worksheet at {path}. Run 'subjects' first.")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_worksheet(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def apply_worksheet(worksheet: Path, vocabulary_path: Path) -> int:
    """Copy decided Q-ids into the tag section of vocabulary.json.

    Only rows whose ``kind`` is ``subject`` are applied. A catch-all or a form
    tag with a Q-id in it is a decision that has not been made, or one that
    belongs on P31 rather than P921, so it is reported and skipped.
    """
    rows = read_worksheet(worksheet)
    vocabulary = json.loads(vocabulary_path.read_text(encoding="utf-8"))
    tags = vocabulary.setdefault("tag", {})

    applied = skipped = unknown = 0
    for row in rows:
        qid = row.get("qid", "").strip()
        if not qid:
            continue
        if not re.fullmatch(r"Q\d+", qid):
            print(f"  not a Q-id, skipped: {row['tag']} = {qid}", file=sys.stderr)
            unknown += 1
            continue
        if row.get("kind") != "subject":
            print(f"  {row['kind']}, not applied to P921: {row['tag']}",
                  file=sys.stderr)
            skipped += 1
            continue
        if row["tag"] not in tags:
            print(f"  not a tag in the data, skipped: {row['tag']}",
                  file=sys.stderr)
            unknown += 1
            continue
        tags[row["tag"]] = qid
        applied += 1

    vocabulary_path.write_text(
        json.dumps(vocabulary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"{applied} tags resolved, {skipped} not subjects, {unknown} unknown "
          f"-> {vocabulary_path}", file=sys.stderr)
    return applied


def run(rows: list[dict], *, output: Path = DEFAULT_OUTPUT,
        tags_md: Path = DEFAULT_TAGS_MD, suggest: bool = False,
        all_rows: list[dict] | None = None) -> Path:
    notes = parse_tag_notes(tags_md)
    software = collect_tags(rows)          # the 416 software entries
    everything = collect_tags(all_rows) if all_rows else software  # all 562

    examples: dict[str, list[str]] = {}
    for row in sorted(rows, key=lambda r: r["name"].lower()):
        for tag in row["tags"].split("|"):
            if tag:
                examples.setdefault(tag, []).append(row["name"])

    previous = {r["tag"]: r for r in read_worksheet(output)} \
        if output.is_file() else {}
    worksheet = build_worksheet(software, everything, notes, examples, previous)

    if suggest:
        print("  asking Wikidata for candidates", file=sys.stderr)
        add_candidates(worksheet)

    write_worksheet(worksheet, output)

    resolved = sum(1 for r in worksheet if r["qid"])
    subjects = sum(1 for r in worksheet if r["kind"] == "subject")
    without_note = [r["tag"] for r in worksheet if not r["scope_note"]]
    print(f"{len(worksheet)} tags, {subjects} of them subjects, "
          f"{resolved} resolved -> {output}", file=sys.stderr)
    print(f"  scope notes from tags.md for "
          f"{len(worksheet) - len(without_note)} of {len(worksheet)}",
          file=sys.stderr)
    if without_note:
        print(f"  without one: {', '.join(without_note)}", file=sys.stderr)
    return output


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT,
                        help="worksheet to write or update "
                             "(default: out/tag-reconciliation.csv)")
    parser.add_argument("--tags-md", type=Path, default=DEFAULT_TAGS_MD,
                        help="the file holding the scope notes")
    parser.add_argument("--suggest", action="store_true",
                        help="fill qid_label with Wikidata search hits. Never "
                             "fills qid itself")
    parser.add_argument("--apply", action="store_true",
                        help="read the filled worksheet back into "
                             "vocabulary.json instead of writing it")

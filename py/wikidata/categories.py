#!/usr/bin/env python3
"""Turn the open-archaeo categories into a class vocabulary.

    python py/wikidata/main.py categories            # write the worksheet
    python py/wikidata/main.py categories --suggest  # with Wikidata candidates
    python py/wikidata/main.py categories --apply    # read it back into vocabulary.json

``unresolved-class`` is one of the two issues that block every single item: the
chublet class says an item belongs to this effort, and nothing at all says what
kind of software it is. The category column knows -- but *Packages and
libraries* is open-archaeo's phrase, not a Wikidata item, and choosing the item
is a judgement.

So it gets the same treatment as the subject tags: a worksheet with one row per
value, the counts that say how much rides on each decision, three example tools
for sanity, and one column to fill. Seven rows in total, which is why this is
worth doing once and properly.

**Deliberately not sliced, and not limited to the software subset.** The
categories are a property of open-archaeo as a whole -- *Guides* and *Lists and
datasets* describe entries this import does not touch yet, but they will be the
same items when it does, and deciding them together keeps one term from
acquiring two Q-ids. ``--apply`` only writes the three software categories into
``item_class``; the rest are recorded for later.
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
DEFAULT_OUTPUT = ROOT / "out" / "category-reconciliation.csv"

COLUMNS = [
    "section", "value", "kind", "uses_software", "uses_all", "examples",
    "search_term", "qid", "qid_label", "note",
]

# The three categories this import writes. The others exist in open-archaeo and
# are carried in the worksheet so the decision is made once for the register as
# a whole, not once per import.
SOFTWARE_CATEGORIES = ["Packages and libraries", "Standalone software", "Scripts"]

# Where the phrase in the register is not what you would search Wikidata for.
SEARCH_OVERRIDES = {
    "Packages and libraries": "software library",
    "Standalone software": "application software",
    "Scripts": "script",
    "Lists and datasets": "data set",
    "Guides": "guide",
    "Products": "product",
    "Specifications, protocols and schemas": "specification",
}

# Notes that say what the decision actually is, since open-archaeo carries no
# definition of its own categories anywhere in the repository.
NOTES = {
    "Packages and libraries": (
        "Code meant to be called by other code. The natural reading is a "
        "software library rather than a distribution format -- an R package on "
        "CRAN is a library that happens to ship as a package."),
    "Standalone software": (
        "Runs on its own. Application software is the usual item; note that "
        "some entries here are extensions of a host application and are better "
        "described by P1547 than by this class."),
    "Scripts": (
        "A single file or small set of them, run rather than installed. "
        "Whether Wikidata has an item that means this and not 'script' in the "
        "writing-system sense is the thing to check."),
    "Lists and datasets": "Not imported yet. Decided here so the term keeps one item.",
    "Guides": "Not imported yet. Documentation rather than software.",
    "Products": "Not imported yet. Ambiguous in the register itself.",
    "Specifications, protocols and schemas": "Not imported yet.",
}

# Values applied to every item regardless of category. The chublet class is
# documented as a subclass of Q73899440, so stating that superclass on each item
# as well is redundant for any query written wdt:P31/wdt:P279* -- which is why
# it is a decision in this sheet rather than a constant in model.py.
SUPERCLASSES = {
    "research software": (
        "Q141115627 is documented as a subclass of Q73899440. If that P279 "
        "holds, stating it on every item too is redundant for queries written "
        "wdt:P31/wdt:P279*. Leave the qid empty to state only the chublet "
        "class; fill it to state both."),
}


def collect(rows: list[dict]) -> Counter:
    return Counter(row["category"] for row in rows if row.get("category"))


def build_worksheet(software: Counter, everything: Counter,
                    examples: dict[str, list[str]],
                    previous: dict[str, dict] | None = None) -> list[dict]:
    """One row per category, then one per superclass. Decisions carry over."""
    previous = previous or {}
    rows = []
    ordered = [c for c in SOFTWARE_CATEGORIES if c in everything]
    ordered += [c for c, _ in everything.most_common() if c not in ordered]

    for value in ordered:
        old = previous.get(value, {})
        rows.append({
            "section": "item_class",
            "value": value,
            "kind": "software" if value in SOFTWARE_CATEGORIES else "other",
            "uses_software": software.get(value, 0),
            "uses_all": everything.get(value, 0),
            "examples": "; ".join(examples.get(value, [])[:3]),
            "search_term": old.get("search_term") or SEARCH_OVERRIDES.get(
                value, value.lower()),
            "qid": old.get("qid", ""),
            "qid_label": old.get("qid_label", ""),
            "note": old.get("note") or NOTES.get(value, ""),
        })

    for value, note in SUPERCLASSES.items():
        old = previous.get(value, {})
        rows.append({
            "section": "superclass",
            "value": value,
            "kind": "every item",
            "uses_software": sum(software.get(c, 0) for c in SOFTWARE_CATEGORIES),
            "uses_all": sum(everything.values()),
            "examples": "",
            "search_term": old.get("search_term") or value,
            "qid": old.get("qid", ""),
            "qid_label": old.get("qid_label", ""),
            "note": old.get("note") or note,
        })
    return rows


def add_candidates(rows: list[dict], limit: int = 3) -> None:
    """Fill qid_label with Wikidata search hits, never the qid itself.

    Same principle as everywhere else here: a search is a good way to find a
    candidate and a bad way to choose one.
    """
    from api import WikidataError, search_entities

    for row in rows:
        if row["qid"] or not row["search_term"]:
            continue
        try:
            hits = search_entities(row["search_term"], limit=limit)
        except WikidataError as error:
            print(f"  search failed for {row['value']}: {error}", file=sys.stderr)
            continue
        row["qid_label"] = " | ".join(
            f"{h['id']} {h.get('label', '')}"
            + (f" ({h['description']})" if h.get("description") else "")
            for h in hits) or "(no hits)"


def read_worksheet(path: Path) -> list[dict]:
    if not path.is_file():
        sys.exit(f"error: no worksheet at {path}. Run 'categories' first.")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_worksheet(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def apply_worksheet(worksheet: Path, vocabulary_path: Path) -> int:
    """Copy decided Q-ids into vocabulary.json.

    Only the three software categories reach ``item_class``: a Q-id on *Guides*
    is a decision recorded for later, not a class this import writes.
    """
    rows = read_worksheet(worksheet)
    vocabulary = json.loads(vocabulary_path.read_text(encoding="utf-8"))

    applied = deferred = unknown = 0
    for row in rows:
        qid = row.get("qid", "").strip()
        if not qid:
            continue
        if not re.fullmatch(r"Q\d+", qid):
            print(f"  not a Q-id, skipped: {row['value']} = {qid}",
                  file=sys.stderr)
            unknown += 1
            continue
        section = row.get("section", "item_class")
        if section == "item_class" and row["value"] not in SOFTWARE_CATEGORIES:
            print(f"  not an imported category, recorded but not applied: "
                  f"{row['value']}", file=sys.stderr)
            deferred += 1
            continue
        target = vocabulary.setdefault(section, {})
        if row["value"] not in target:
            print(f"  not a value in the data, skipped: {section}/{row['value']}",
                  file=sys.stderr)
            unknown += 1
            continue
        target[row["value"]] = qid
        applied += 1

    vocabulary_path.write_text(
        json.dumps(vocabulary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"{applied} values resolved, {deferred} recorded for later, "
          f"{unknown} unknown -> {vocabulary_path}", file=sys.stderr)
    return applied


def verify_worksheet(rows: list[dict]) -> int:
    """Say, with evidence, whether a filled-in Q-id is the right one.

    A search hit tells you an item exists with a matching label. That is not
    the question. The question is whether the item is a *class that other
    software items are already instances of* -- and three things answer it:

    * what the item actually says it is, in its own label and description;
    * whether it is a class at all, or a scholarly article or a patent whose
      title happens to match, which is what the second and third search hits
      usually are;
    * how many items already use it as a ``P31`` value. A class in real use is
      a safer choice than a technically defensible one nobody states, because
      the point of the statement is to put these tools where people looking for
      tools will find them.

    Returns the number of rows that need a second look.
    """
    from api import WikidataError, get_entities, sparql

    filled = [row for row in rows if row.get("qid", "").strip()]
    if not filled:
        print("no qid filled in yet -- nothing to verify", file=sys.stderr)
        return 0

    qids = sorted({row["qid"].strip() for row in filled})
    try:
        entities = get_entities(qids, props="info|labels|descriptions|claims")
    except WikidataError as error:
        print(f"cannot read the items: {error}", file=sys.stderr)
        return len(filled)

    counts: dict[str, int] = {}
    try:
        block = " ".join(f"wd:{q}" for q in qids)
        for result in sparql(f"""
SELECT ?class (COUNT(DISTINCT ?item) AS ?uses) WHERE {{
  VALUES ?class {{ {block} }}
  ?item wdt:P31 ?class .
}}
GROUP BY ?class"""):
            counts[result["class"].rsplit("/", 1)[-1]] = int(result["uses"])
    except WikidataError as error:
        print(f"  usage counts unavailable ({error})", file=sys.stderr)

    # Items that are almost never what you want as a P31 value here. A search
    # for "software library" returns the patent and the article about one.
    NOT_A_CLASS = {
        "Q13442814": "scholarly article", "Q253623": "patent",
        "Q4167410": "disambiguation page", "Q7318358": "review article",
        "Q5633421": "scientific journal", "Q101352": "family name",
        "Q3305213": "painting", "Q11424": "film",
    }

    doubtful = 0
    for row in filled:
        qid = row["qid"].strip()
        entity = entities.get(qid, {})
        if entity.get("missing") is not None or "id" not in entity:
            print(f"\n{row['value']}\n  {qid} does not exist", file=sys.stderr)
            doubtful += 1
            continue

        label = entity.get("labels", {}).get("en", {}).get("value", "")
        description = entity.get("descriptions", {}).get("en", {}).get("value", "")
        claims = entity.get("claims", {})
        instance_of = [snak.get("mainsnak", {}).get("datavalue", {})
                       .get("value", {}).get("id", "")
                       for snak in claims.get("P31", [])]
        is_class = bool(claims.get("P279")) or bool(counts.get(qid))
        wrong_kind = [NOT_A_CLASS[q] for q in instance_of if q in NOT_A_CLASS]
        uses = counts.get(qid, 0)

        print(f"\n{row['value']}  ->  {qid}")
        print(f"  label        {label or '(none)'}")
        print(f"  description  {description or '(none)'}")
        print(f"  used as P31  {uses} items" if uses
              else "  used as P31  never -- no item states it")
        print(f"  subclass of  {'yes' if claims.get('P279') else 'no P279'}")

        problems = []
        if wrong_kind:
            problems.append("this is a " + ", ".join(wrong_kind)
                            + ", not a class")
        if not is_class:
            problems.append("neither a subclass of anything nor used as P31 "
                            "by any item")
        if uses and uses < 5:
            problems.append(f"only {uses} items use it; a barely-used class "
                            "may be the wrong one, or a duplicate of the "
                            "right one")
        for problem in problems:
            print(f"  ! {problem}")
        if problems:
            doubtful += 1
        else:
            print("  ok")

    print(f"\n{len(filled)} filled, {doubtful} worth a second look",
          file=sys.stderr)
    return doubtful


def run(rows: list[dict], *, output: Path = DEFAULT_OUTPUT,
        suggest: bool = False, all_rows: list[dict] | None = None) -> Path:
    software = collect(rows)
    everything = collect(all_rows) if all_rows else software

    examples: dict[str, list[str]] = {}
    for row in sorted(all_rows or rows, key=lambda r: r["name"].lower()):
        examples.setdefault(row["category"], []).append(row["name"])

    previous = {r["value"]: r for r in read_worksheet(output)} \
        if output.is_file() else {}
    worksheet = build_worksheet(software, everything, examples, previous)

    if suggest:
        print("  asking Wikidata for candidates", file=sys.stderr)
        add_candidates(worksheet)

    write_worksheet(worksheet, output)

    resolved = sum(1 for r in worksheet if r["qid"])
    blocking = [r for r in worksheet
                if r["section"] == "item_class" and r["kind"] == "software"
                and not r["qid"]]
    print(f"{len(worksheet)} values, {resolved} resolved -> {output}",
          file=sys.stderr)
    if blocking:
        entries = sum(r["uses_software"] for r in blocking)
        print(f"  {len(blocking)} of them block {entries} entries: "
              f"{', '.join(r['value'] for r in blocking)}", file=sys.stderr)
    return output


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT,
                        help="worksheet to write or update "
                             "(default: out/category-reconciliation.csv)")
    parser.add_argument("--suggest", action="store_true",
                        help="fill qid_label with Wikidata search hits. Never "
                             "fills qid itself")
    parser.add_argument("--apply", action="store_true",
                        help="read the filled worksheet back into "
                             "vocabulary.json instead of writing it")
    parser.add_argument("--verify", action="store_true",
                        help="check the Q-ids already filled in: what each item "
                             "says it is, and how many items use it as P31. "
                             "Read-only")

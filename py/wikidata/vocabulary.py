#!/usr/bin/env python3
"""The registry mapping open-archaeo's controlled strings to Q-ids.

P277, P1547, P921 and the P8423 qualifier all take *items* as values, and
open-archaeo gives strings. ``vocabulary.json`` is where one becomes the other:
every value starts as ``null`` and stays that way until a person fills it in.

Nothing here ever writes a Q-id by itself. Label search is a good way to find a
candidate and a bad way to choose one.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from api import search_entities
from model import (
    CATEGORY_CLASSES, FORGE_VCS, SUPERCLASSES, VOCABULARY_SECTIONS,
)

DEFAULT_PATH = Path(__file__).resolve().parent / "vocabulary.json"

PLATFORM_SECTION = {
    "language": "programming_language",
    "host application": "host_application",
    "deployment": "deployment",
}


def scaffold(rows: list[dict]) -> dict:
    """Collect every controlled value that needs a Q-id, with null for unknown."""
    vocabulary: dict = {
        "_note": (
            "Q-ids for the controlled values of open-archaeo. null means "
            "unresolved; the push step skips a statement whose value is "
            "unresolved rather than guessing. Fill in by hand, or run "
            "'python py/wikidata/main.py vocab --suggest' for candidates."
        ),
        "_sections": VOCABULARY_SECTIONS,
    }
    for section in VOCABULARY_SECTIONS:
        vocabulary[section] = {}

    for host in sorted({h for row in rows
                        for h in row["repository_host"].split("|") if h}):
        vocabulary["version_control_system"][FORGE_VCS.get(host, host)] = None
    vocabulary["version_control_system"].pop("", None)

    for row in rows:
        section = PLATFORM_SECTION.get(row["platform_role"])
        if section and row["platform"]:
            vocabulary[section].setdefault(row["platform"], None)
        for tag in row["tags"].split("|"):
            if tag:
                vocabulary["tag"].setdefault(tag, None)

    # The category classes and the superclasses are known in advance -- what is
    # unknown is which items they map to, which is exactly what this file is
    # for. Seeding them means an unresolved class shows up as a red issue on
    # the preview rather than as silence.
    for category in CATEGORY_CLASSES:
        vocabulary["item_class"].setdefault(category, None)
    for label in SUPERCLASSES:
        vocabulary["superclass"].setdefault(label, None)

    for section in VOCABULARY_SECTIONS:
        vocabulary[section] = dict(sorted(vocabulary[section].items()))
    return vocabulary


def merge(fresh: dict, existing: dict) -> dict:
    """Keep every Q-id already resolved; add whatever is new in the data."""
    for section in VOCABULARY_SECTIONS:
        for key, value in existing.get(section, {}).items():
            if value and key in fresh[section]:
                fresh[section][key] = value
    return fresh


def unresolved(vocabulary: dict) -> dict[str, list[str]]:
    return {section: [k for k, v in vocabulary[section].items() if not v]
            for section in VOCABULARY_SECTIONS}


def suggest(vocabulary: dict, *, limit: int = 3) -> None:
    """Print Wikidata search hits for every unresolved value. Writes nothing."""
    for section, terms in unresolved(vocabulary).items():
        if not terms:
            continue
        print(f"\n== {section} ({len(terms)} unresolved) ==")
        for term in terms:
            hits = search_entities(term, limit=limit)
            print(f"\n{term}")
            for hit in hits:
                print(f"    {hit['id']:<12} {hit.get('label', '')} -- "
                      f"{hit.get('description', '')}")
            if not hits:
                print("    (no hits)")


def resolve(vocabulary: dict, assignments: list[list[str]]) -> int:
    """Set ``SECTION VALUE QID`` triples in the registry.

    Editing the JSON by hand works too, but one wrong bracket makes every step
    fail with a parse error rather than with the thing you got wrong. This
    validates instead: the section has to exist, the value has to be one the
    data actually contains, and the Q-id has to look like one.
    """
    applied = 0
    for section, value, qid in assignments:
        if section not in vocabulary:
            print(f"  no such section: {section} -- try one of "
                  f"{', '.join(sorted(k for k in vocabulary if not k.startswith('_')))}",
                  file=sys.stderr)
            continue
        if value not in vocabulary[section]:
            near = [k for k in vocabulary[section] if k.lower() == value.lower()]
            if near:
                value = near[0]
            else:
                print(f"  not a value in {section}: {value}", file=sys.stderr)
                continue
        if not re.fullmatch(r"Q\d+", qid):
            print(f"  not a Q-id: {qid}", file=sys.stderr)
            continue
        previous = vocabulary[section][value]
        vocabulary[section][value] = qid
        note = f" (was {previous})" if previous and previous != qid else ""
        print(f"  {section}/{value} = {qid}{note}", file=sys.stderr)
        applied += 1
    return applied


def load(path: Path = DEFAULT_PATH) -> dict:
    if not path.is_file():
        sys.exit(f"error: no vocabulary at {path}. Run 'vocab' first.")
    return json.loads(path.read_text(encoding="utf-8"))


def save(vocabulary: dict, path: Path = DEFAULT_PATH) -> None:
    path.write_text(json.dumps(vocabulary, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")

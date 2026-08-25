#!/usr/bin/env python3
"""Match open-archaeo entries against Wikidata and keep the concordance.

The concordance is ``out/open-archaeo-concordance.csv``: the transformed table
plus the Q-id and how it was found. It is the file that answers "what is
already in Wikidata", and every later step reads it rather than querying again.
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

from api import chunks, sparql
from model import (
    CHUBLET_CLASS, CHUBLET_WIKIPROJECT, CONCORDANCE_EXTRA, P_CRAN, P_DOI,
    P_INSTANCE_OF, P_MAINTAINED_BY_WIKIPROJECT, P_PYPI, P_REPOSITORY,
    package_name, repository_variants,
)

CONCORDANCE_NAME = "open-archaeo-concordance.csv"

LABEL_SERVICE = 'SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de". }'


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def match_by_iri(values: list[str], prop: str) -> dict[str, tuple[str, str]]:
    """Look up items by an IRI-valued property (url datatype)."""
    found: dict[str, tuple[str, str]] = {}
    for chunk in chunks(values):
        block = " ".join(f"<{v}>" for v in chunk)
        for row in sparql(f"""
SELECT ?value ?item ?itemLabel WHERE {{
  VALUES ?value {{ {block} }}
  ?item wdt:{prop} ?value .
  {LABEL_SERVICE}
}}"""):
            found[row["value"]] = (_qid(row["item"]), row.get("itemLabel", ""))
    return found


def match_by_literal(values: list[str], prop: str) -> dict[str, tuple[str, str]]:
    """Look up items by a literal-valued property (external-id, string)."""
    found: dict[str, tuple[str, str]] = {}
    for chunk in chunks(values):
        block = " ".join('"' + v.replace('"', '\\"') + '"' for v in chunk)
        for row in sparql(f"""
SELECT ?value ?item ?itemLabel WHERE {{
  VALUES ?value {{ {block} }}
  ?item wdt:{prop} ?value .
  {LABEL_SERVICE}
}}"""):
            found[row["value"]] = (_qid(row["item"]), row.get("itemLabel", ""))
    return found


def existing_chublets() -> set[str]:
    """Q-ids already carrying both of the two obligatory statements."""
    return {_qid(row["item"]) for row in sparql(f"""
SELECT ?item WHERE {{
  ?item wdt:{P_INSTANCE_OF} wd:{CHUBLET_CLASS} ;
        wdt:{P_MAINTAINED_BY_WIKIPROJECT} wd:{CHUBLET_WIKIPROJECT} .
}}""")}


def reconcile(rows: list[dict], *, use_registries: bool = True) -> list[dict]:
    """Attach a Q-id to every row, in place, and return the rows.

    Four keys are tried in decreasing order of confidence: repository URL, DOI,
    CRAN package, PyPI package. Names are deliberately **not** used -- a shared
    name is exactly what open-archaeo's own slug disambiguation has to work
    around, so matching on it would manufacture false positives at the rate the
    duplicates occur.
    """
    for row in rows:
        row.update({key: "" for key in CONCORDANCE_EXTRA})

    wanted: dict[str, list[dict]] = {}
    for row in rows:
        for url in row["repository"].split("|"):
            for variant in repository_variants(url):
                wanted.setdefault(variant, []).append(row)
    if wanted:
        print(f"  {len(wanted)} repository spellings -> {P_REPOSITORY}",
              file=sys.stderr)
        for value, (qid, label) in match_by_iri(sorted(wanted), P_REPOSITORY).items():
            for row in wanted[value]:
                if not row["qid"]:
                    row.update(qid=qid, match_property=P_REPOSITORY,
                               match_value=value, wikidata_label=label)

    # Wikidata stores DOIs upper-case.
    todo = {r["doi"].upper(): r for r in rows if r["doi"] and not r["qid"]}
    if todo:
        print(f"  {len(todo)} DOIs -> {P_DOI}", file=sys.stderr)
        for value, (qid, label) in match_by_literal(sorted(todo), P_DOI).items():
            if not todo[value]["qid"]:
                todo[value].update(qid=qid, match_property=P_DOI,
                                   match_value=value, wikidata_label=label)

    if use_registries:
        for prop, pattern in ((P_CRAN, r"package=([^/&?]+)"),
                              (P_PYPI, r"pypi\.org/project/([^/?#]+)")):
            todo = {}
            for row in rows:
                if row["qid"] or not row["registry"]:
                    continue
                name = package_name(row["registry"], pattern)
                if name:
                    todo[name] = row
            if not todo:
                continue
            print(f"  {len(todo)} packages -> {prop}", file=sys.stderr)
            for value, (qid, label) in match_by_literal(sorted(todo), prop).items():
                if not todo[value]["qid"]:
                    todo[value].update(qid=qid, match_property=prop,
                                       match_value=value, wikidata_label=label)

    tagged = existing_chublets()
    print(f"  {len(tagged)} items already carry both obligatory statements",
          file=sys.stderr)
    today = date.today().isoformat()
    for row in rows:
        row["checked"] = today
        if row["qid"]:
            row["is_chublet"] = "yes" if row["qid"] in tagged else "no"
    return rows


def load_concordance(path: Path) -> list[dict]:
    if not path.is_file():
        sys.exit(f"error: no concordance at {path}. Run 'reconcile' first.")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def merge_concordance(fresh: list[dict], previous: list[dict]) -> list[dict]:
    """Carry manually curated Q-ids over into a fresh run.

    A Q-id written by hand -- ``match_property`` empty or ``manual`` -- is a
    curation decision and outranks anything a lookup produces, so it survives a
    rebuild. Everything else is recomputed.
    """
    kept = {row["id"]: row for row in previous
            if row.get("qid") and row.get("match_property", "") in ("", "manual")}
    for row in fresh:
        old = kept.get(row["id"])
        if old:
            row.update(qid=old["qid"], match_property="manual",
                       match_value=old.get("match_value", ""),
                       wikidata_label=old.get("wikidata_label", ""))
    return fresh

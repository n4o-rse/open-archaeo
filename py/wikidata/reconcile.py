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
    CONCORDANCE_EXTRA, IDENTITY_STATEMENTS, OPEN_ARCHAEO, P_COLLECTION, P_CRAN,
    P_DOI, P_EXACT_MATCH, P_INVENTORY_NUMBER, P_PYPI, P_REPOSITORY,
    package_name, post_url, repository_variants,
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


def match_by_slug(slugs: list[str]) -> dict[str, tuple[str, str]]:
    """Look up items by the open-archaeo slug in P217, read in its collection.

    An inventory number only means something against the register it belongs
    to, so the qualifier is part of the query rather than an afterthought:
    matching on P217 alone would accept a museum object numbered ``tabula``.
    """
    found: dict[str, tuple[str, str]] = {}
    # Smaller batches than the other lookups: this one walks statement nodes
    # rather than truthy triples, which costs the query service noticeably more
    # per value, and a batch that times out costs everything in it.
    for chunk in chunks(slugs, 50):
        block = " ".join('"' + v.replace('"', '\\"') + '"' for v in chunk)
        for row in sparql(f"""
SELECT ?value ?item ?itemLabel WHERE {{
  VALUES ?value {{ {block} }}
  ?item p:{P_INVENTORY_NUMBER} ?statement .
  ?statement ps:{P_INVENTORY_NUMBER} ?value ;
             pq:{P_COLLECTION} wd:{OPEN_ARCHAEO} .
  {LABEL_SERVICE}
}}"""):
            found[row["value"]] = (_qid(row["item"]), row.get("itemLabel", ""))
    return found


def existing_chublets() -> set[str]:
    """Q-ids already carrying the whole item-valued identity block.

    Built from ``IDENTITY_STATEMENTS`` rather than written out, so adding a
    statement to the block cannot leave this query behind asking the old
    question.
    """
    pattern = " ;\n        ".join(
        f"wdt:{prop} wd:{qid}" for prop, qid, _ in IDENTITY_STATEMENTS)
    return {_qid(row["item"]) for row in sparql(f"""
SELECT ?item WHERE {{
  ?item {pattern} .
}}""")}


def reconcile(rows: list[dict], *, use_registries: bool = True) -> list[dict]:
    """Attach a Q-id to every row, in place, and return the rows.

    Six keys are tried in decreasing order of confidence. The first two are the
    identity block reading itself back: an item that already carries the entry
    URL in P2888, or the slug in P217 within the open-archaeo collection, *is*
    this entry -- no inference involved, which is why they run before the
    repository URL. The other four look outward: repository URL, DOI, CRAN
    package, PyPI package.

    Names are deliberately **not** used -- a shared name is exactly what
    open-archaeo's own slug disambiguation has to work around, so matching on
    it would manufacture false positives at the rate the duplicates occur.
    """
    for row in rows:
        row.update({key: "" for key in CONCORDANCE_EXTRA})

    by_url = {post_url(r["slug"]): r for r in rows if r.get("slug")}
    if by_url:
        print(f"  {len(by_url)} entry URLs -> {P_EXACT_MATCH}", file=sys.stderr)
        for value, (qid, label) in match_by_iri(sorted(by_url), P_EXACT_MATCH).items():
            by_url[value].update(qid=qid, match_property=P_EXACT_MATCH,
                                 match_value=value, wikidata_label=label)

    by_slug = {r["slug"]: r for r in rows if r.get("slug") and not r["qid"]}
    if by_slug:
        print(f"  {len(by_slug)} slugs -> {P_INVENTORY_NUMBER} in "
              f"{P_COLLECTION} {OPEN_ARCHAEO}", file=sys.stderr)
        for value, (qid, label) in match_by_slug(sorted(by_slug)).items():
            if not by_slug[value]["qid"]:
                by_slug[value].update(qid=qid, match_property=P_INVENTORY_NUMBER,
                                      match_value=value, wikidata_label=label)

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
    print(f"  {len(tagged)} items already carry the whole identity block",
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

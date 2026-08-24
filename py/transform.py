#!/usr/bin/env python3
"""Reshape the open-archaeo dataset into one machine-readable table.

This module owns everything that turns the raw CSV into something a downstream
consumer can read: identifier minting, the collapsed one-row-per-entry table
and the data README that documents it.

It is driven by ``py/main.py`` but runs standalone as well::

    python py/transform.py --out-dir out/
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "open-archaeo.csv"
OUTPUT_NAME = "open-archaeo-software.csv"

# Base URL of the published site; a slug resolves to BASE + slug + "/".
POST_BASE_URL = "https://open-archaeo.info/post/"

# Length of the minted hexadecimal identifier. Six characters give 16.7M
# values; the collision check in ``mint_ids`` fails loudly if that is not
# enough for the dataset at hand.
ID_LENGTH = 6

TAG_COLUMNS = ["tag1", "tag2", "tag3", "tag4", "tag5"]
AUTHOR_COLUMNS = [f"author{i}_name" for i in range(1, 7)]

# Forge columns, collapsed into ``repository`` + ``repository_host``.
FORGE_COLUMNS = ["github", "gist", "gitlab", "bitbucket", "launchpad", "codeberg"]
FORGE_LABELS = {
    "github": "GitHub", "gist": "GitHub Gist", "gitlab": "GitLab",
    "bitbucket": "Bitbucket", "launchpad": "Launchpad", "codeberg": "Codeberg",
}

# Package registry columns, collapsed into ``registry`` + ``registry_name``.
REGISTRY_COLUMNS = {"cran": "CRAN", "pypi": "PyPI"}

# ``platform`` conflates three things that Wikidata keeps apart: the language
# an entry is written in, the application it runs inside, and the form it is
# delivered as. ``platform_role`` is derived so each maps to its own property.
# Edit this table rather than the code below.
PLATFORM_ROLES = {
    # written in this language -> P277 programmed in
    "R": "language", "Python": "language", "MATLAB": "language",
    "JavaScript": "language", "Ruby": "language", "Lisp": "language",
    "C": "language", "Java": "language", "LaTeX": "language",
    "NetLogo": "language",
    # runs inside this application -> P1547 depends on software
    "QGIS": "host application", "ArcGIS": "host application",
    "Blender": "host application", "LibreOffice Calc": "host application",
    "Microsoft Excel": "host application", "Stellarium": "host application",
    "Meshlab": "host application", "AutoCAD": "host application",
    "Piwigo": "host application", "Open Data Kit": "host application",
    # delivered in this form -> refines P31, not a platform statement
    "Mobile app": "deployment", "Web app": "deployment",
}

# The three categories describing software rather than documentation or data
# collections; the subset intended for the Wikidata import.
SOFTWARE_CATEGORIES = ["Packages and libraries", "Standalone software", "Scripts"]

# All link-bearing source columns, in the order they are consulted.
LINK_COLUMNS = FORGE_COLUMNS + [
    "cran", "pypi", "website", "publication", "DOI",
    "blogpost", "youtube", "twitter", "internetarchive",
]

# Documentation of the output columns, used to generate out/README.md.
# Each entry is (source, description, suggested Wikidata property).
# P1324, P856 and P356 are verified against Wikidata; the rest are modelling
# decisions, flagged as such in the generated table.
COLUMN_DOCS: dict[str, tuple[str, str, str]] = {
    "id": ("derived",
           "Six hexadecimal characters, `sha256(slug)` truncated. Unique "
           "across all 562 source entries.", ""),
    "slug": ("derived",
             "Path segment under which the entry is published on "
             "open-archaeo.info.", ""),
    "url": ("derived",
            "Resolvable page, base URL plus slug, percent-encoded.",
            "P973?"),
    "name": ("`item_name`",
             "Name of the tool as recorded upstream. Not unique.",
             "label"),
    "description": ("`description`",
                    "One or two sentences describing the tool. Sentence case "
                    "with terminal punctuation, so it needs rewriting before "
                    "it can serve as a Wikidata description.", ""),
    "category": ("`category`",
                 "One of the three software categories. Determines the class, "
                 "which is a choice: software library (Q188860), application "
                 "software (Q166142), software (Q7397).", "P31?"),
    "platform": ("`platform`",
                 "Language, host application or delivery form. See "
                 "`platform_role`.", ""),
    "platform_role": ("derived",
                      "Which of the three `platform` means: `language`, "
                      "`host application`, `deployment`, or empty. Routes the "
                      "value to P277, P1547 or a P31 refinement respectively.",
                      ""),
    "tags": ("`tag1`–`tag5`",
             "Thematic subjects from a 59-value vocabulary, pipe-separated, "
             "zero to five per entry. Each term needs reconciling to an item.",
             "P921?"),
    "authors": ("`author1_name`–`author6_name`",
                "Pipe-separated, in upstream order. Mostly forge usernames "
                "rather than personal names, so P2037 is a more reliable "
                "route than matching a name string to P178.", "P2037?"),
    "repository": ("`github`, `gist`, `gitlab`, `bitbucket`, `launchpad`, "
                   "`codeberg`",
                   "Pipe-separated repository URLs.", "P1324"),
    "repository_host": ("derived",
                        "Parallel to `repository`, so each URL keeps its "
                        "host. Can drive the P8423 version control system "
                        "qualifier: Git for GitHub, GitLab and Codeberg; "
                        "Bazaar for Launchpad; Bitbucket is ambiguous.", ""),
    "registry": ("`cran`, `pypi`", "Package registry page.", "P973?"),
    "registry_name": ("derived",
                      "Parallel to `registry`: `CRAN` or `PyPI`.", ""),
    "doi": ("`DOI`",
            "Normalised to the bare `10.x/…` form, any `https://doi.org/` "
            "prefix removed.", "P356"),
    "publication": ("`publication`",
                    "URL of an accompanying paper, often itself a `doi.org` "
                    "link. P1343 with an item would be richer than a bare URL.",
                    "P973?"),
    "website": ("`website`", "Project homepage or documentation site.", "P856"),
    "blogpost": ("`blogpost`", "A blog post about the tool.", "P973?"),
    "youtube": ("`youtube`", "A video about the tool.", "P973?"),
    "twitter": ("`twitter`",
                "Carried for losslessness. P2002 expects a username, not a "
                "URL, so this is not import material as it stands.", ""),
    "internetarchive": ("`internetarchive`",
                        "Internet Archive snapshot of the repository. "
                        "Normally a qualifier on P1324 rather than a "
                        "statement of its own.", "P1065?"),
    "notes": ("`notes`",
              "Editorial notes by the open-archaeo maintainers **about the "
              "dataset**, not about the tool. Not import material.", ""),
}

SIMPLE_COLUMNS = list(COLUMN_DOCS)


# --------------------------------------------------------------------------
# Slugs and identifiers
# --------------------------------------------------------------------------

def clean_slug(name: str) -> str:
    """Port of ``clean_slug()`` in R/site.R.

    Deliberately identical to the upstream R implementation, including its
    quirks: only a trailing ``.r`` is stripped, and no characters other than
    space, underscore, dot and slash are touched.
    """
    slug = name.lower()
    slug = re.sub(r"\.r$", "", slug, count=1)
    for char in (" ", "_", ".", "/"):
        slug = slug.replace(char, "-")
    return re.sub(r"--+", "-", slug)


def hugo_sanitize(slug: str) -> str:
    """Apply Hugo's path sanitisation on top of the R slug.

    Hugo drops characters outside its allowed set when turning a filename into
    a URL segment, which the R code does not anticipate. Verified against the
    live site: ``fiche-stratigraphique-numérique-(fsn)`` is published as
    ``fiche-stratigraphique-numérique-fsn`` -- the brackets vanish, the accent
    survives and is percent-encoded only in the URL itself.
    """
    allowed_punctuation = set("./\\_#+~-@")
    kept = [
        char for char in slug
        if char in allowed_punctuation
        or char.isalnum()
        or unicodedata.category(char).startswith("M")
    ]
    return re.sub(r"--+", "-", "".join(kept))


def assign_slugs(records: list[dict]) -> None:
    """Mint the site slug for every record, in place.

    Mirrors ``unique_slug()`` in R/site.R: entries sharing a cleaned slug all
    get their first author appended. Grouping runs over the **whole** dataset,
    never over a filtered subset, or the slugs would stop matching the site.
    """
    for record in records:
        record["slug"] = clean_slug(record["item_name"])

    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[record["slug"]].append(record)

    for group in groups.values():
        if len(group) > 1:
            for record in group:
                record["slug"] = clean_slug(
                    f"{record['slug']}-{record['author1_name']}"
                )

    for record in records:
        record["slug"] = hugo_sanitize(record["slug"])

    duplicates = [s for s, n in Counter(r["slug"] for r in records).items() if n > 1]
    if duplicates:
        sys.exit("error: slugs are not unique: " + ", ".join(duplicates))


def post_url(slug: str) -> str:
    """Resolvable URL of an entry on open-archaeo.info."""
    return f"{POST_BASE_URL}{quote(slug)}/"


def mint_ids(records: list[dict]) -> None:
    """Derive a short hexadecimal identifier from each slug, in place.

    The identifier is a truncated SHA-256 digest, so it is deterministic and
    needs no counter or registry. It is a function *of the slug*: if an entry
    is renamed, or a name collision forces an author suffix, the slug changes
    and so does the identifier. It is therefore a convenient handle, not a
    persistent identifier.
    """
    for record in records:
        digest = hashlib.sha256(record["slug"].encode("utf-8")).hexdigest()
        record["id"] = digest[:ID_LENGTH]

    collisions = [i for i, n in Counter(r["id"] for r in records).items() if n > 1]
    if collisions:
        affected = [r["slug"] for r in records if r["id"] in collisions]
        sys.exit(
            f"error: {ID_LENGTH}-character ids collide for: {', '.join(affected)}. "
            f"Raise ID_LENGTH in py/transform.py."
        )


# --------------------------------------------------------------------------
# Loading and reshaping
# --------------------------------------------------------------------------

def load(csv_path: Path = DEFAULT_CSV) -> list[dict]:
    """Read the dataset and normalise it into flat records.

    Whitespace is stripped, the trailing unnamed column is dropped, tag and
    author columns are collapsed into lists, and slug, url and id are minted.
    """
    if not csv_path.is_file():
        sys.exit(f"error: dataset not found at {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    records = []
    for row in rows:
        record = {
            key: (value or "").strip()
            for key, value in row.items()
            if key  # the file ends on an unnamed empty column
        }
        record["tags"] = [t for t in (record.pop(c, "") for c in TAG_COLUMNS) if t]
        record["authors"] = [a for a in (record[c] for c in AUTHOR_COLUMNS) if a]
        records.append(record)

    assign_slugs(records)  # needs author1_name, so before dropping it
    mint_ids(records)
    for record in records:
        record["url"] = post_url(record["slug"])
        for column in AUTHOR_COLUMNS:
            record.pop(column, None)
    return records


def normalise_doi(value: str) -> str:
    """Reduce a DOI to its bare form -- the shape Wikidata's P356 expects."""
    return re.sub(r"^\s*(https?://(dx\.)?doi\.org/|doi:)", "", value, flags=re.I).strip()


def simplify(record: dict) -> dict:
    """Collapse a record into one output row.

    Six forge columns become ``repository`` plus a parallel
    ``repository_host``; two registry columns become ``registry`` plus
    ``registry_name``; tag and author columns become one field each. No value
    from the source is discarded.
    """
    repos = [(FORGE_LABELS[c], record[c]) for c in FORGE_COLUMNS if record.get(c)]
    registries = [(n, record[c]) for c, n in REGISTRY_COLUMNS.items() if record.get(c)]

    return {
        "id": record["id"],
        "slug": record["slug"],
        "url": record["url"],
        "name": record["item_name"],
        "description": record["description"],
        "category": record["category"],
        "platform": record["platform"],
        "platform_role": PLATFORM_ROLES.get(record["platform"], ""),
        "tags": "|".join(record["tags"]),
        "authors": "|".join(record["authors"]),
        "repository": "|".join(url for _, url in repos),
        "repository_host": "|".join(host for host, _ in repos),
        "registry": "|".join(url for _, url in registries),
        "registry_name": "|".join(name for name, _ in registries),
        "doi": normalise_doi(record["DOI"]),
        "publication": record["publication"],
        "website": record["website"],
        "blogpost": record["blogpost"],
        "youtube": record["youtube"],
        "twitter": record["twitter"],
        "internetarchive": record["internetarchive"],
        "notes": record["notes"],
    }


def to_csv(rows: list[dict], columns: list[str]) -> str:
    """Serialise rows as CSV with a fixed column order."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().rstrip("\n")


# --------------------------------------------------------------------------
# Data README
# --------------------------------------------------------------------------

def render_readme(rows: list[dict], source: Path, categories: list[str] | None) -> str:
    """Generate the documentation that ships beside the CSV.

    The fill counts are computed from the rows actually written, so the
    documentation cannot drift away from the data it describes.
    """
    filled = {col: sum(1 for r in rows if r[col]) for col in SIMPLE_COLUMNS}
    total = len(rows)
    scope = (", ".join(categories) if categories
             else "all categories, including non-software entries")

    lines = [
        f"# `{OUTPUT_NAME}`",
        "",
        "Generated file -- do not edit by hand. Rebuild with:",
        "",
        "```bash",
        "python py/main.py transform",
        "```",
        "",
        "## Provenance",
        "",
        f"- Source: `{source.name}` in the repository root",
        f"- Scope: {scope}",
        f"- Rows: {total}",
        f"- Columns: {len(SIMPLE_COLUMNS)}",
        "",
        "The transformation is lossless with respect to the source: every "
        "non-empty value reappears, only reshaped. Six forge columns collapse "
        "into `repository` plus a parallel `repository_host`, two registry "
        "columns into `registry` plus `registry_name`, and the five tag and "
        "six author columns into one field each.",
        "",
        "Multi-valued fields use `|` as separator. Where two columns are "
        "described as parallel, their values line up position by position.",
        "",
        "## Columns",
        "",
        "`Filled` counts rows with a non-empty value. `Property` is the "
        "suggested Wikidata mapping; entries marked `?` are modelling "
        "decisions rather than settled facts, and P1324, P856 and P356 are "
        "the only ones verified against Wikidata.",
        "",
        "| Column | Source | Filled | Property | Content |",
        "|---|---|---|---|---|",
    ]

    for column in SIMPLE_COLUMNS:
        source_desc, content, prop = COLUMN_DOCS[column]
        lines.append(
            f"| `{column}` | {source_desc} | {filled[column]} | "
            f"{prop or '—'} | {content} |"
        )

    lines += [
        "",
        "## Controlled vocabularies",
        "",
        "| Field | Cardinality | Distinct values in this file |",
        "|---|---|---|",
    ]
    for field, cardinality in [("category", "exactly one"),
                               ("platform", "zero or one"),
                               ("platform_role", "zero or one"),
                               ("tags", "zero to five")]:
        values = set()
        for row in rows:
            values.update(v for v in row[field].split("|") if v)
        lines.append(f"| `{field}` | {cardinality} | {len(values)} |")

    lines += [
        "",
        "## Known gaps",
        "",
        "Wikidata expects several things open-archaeo does not record. These "
        "have to come from the repositories, the registries or Software "
        "Heritage:",
        "",
        "- **Copyright licence (P275).** P1324 carries a constraint that "
        "items should state a licence. This is the largest single gap.",
        "- **Inception (P571)** and **software version (P348)**.",
        f"- **Programming language** for the "
        f"{sum(1 for r in rows if not r['platform'])} rows with an empty "
        "`platform`.",
        "- **Software Heritage identifier.** Listed upstream in `ToDo.md` as "
        "a planned addition.",
        "",
        "Existing Wikidata items should be reconciled before anything is "
        "created; `repository` is the strongest join key, `doi` the second.",
        "",
        "See `py/README.md` for the full audit and the slug derivation.",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Step entry point
# --------------------------------------------------------------------------

def run(csv_path: Path = DEFAULT_CSV, out_dir: Path = ROOT / "out",
        categories: list[str] | None = None) -> list[Path]:
    """Write the table and its documentation; return the paths written."""
    records = load(csv_path)
    if categories is not None:
        records = [r for r in records if r["category"] in set(categories)]

    rows = [simplify(r) for r in records]
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_out = out_dir / OUTPUT_NAME
    readme_out = out_dir / "README.md"

    csv_out.write_text(to_csv(rows, SIMPLE_COLUMNS) + "\n", encoding="utf-8")
    readme_out.write_text(
        render_readme(rows, csv_path, categories) + "\n", encoding="utf-8")

    links = sum(1 for r in records for c in LINK_COLUMNS if r.get(c))
    print(f"{len(rows)} entries, {links} links -> {csv_out}", file=sys.stderr)
    print(f"documentation -> {readme_out}", file=sys.stderr)
    return [csv_out, readme_out]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register this step's options; shared with the orchestrator in main.py."""
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help="path to open-archaeo.csv (default: repository root)")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "out",
                        help="directory for the generated table (default: out/)")
    parser.add_argument("--all-categories", action="store_true",
                        help="keep all 562 entries instead of the software subset")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_arguments(parser)
    args = parser.parse_args(argv)
    run(args.csv, args.out_dir,
        None if args.all_categories else SOFTWARE_CATEGORIES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Single entry point for the open-archaeo processing steps.

Every step is a module next to this file, runnable standalone as well::

    python py/main.py --list                       # available steps
    python py/main.py transform                    # write out/*.csv
    python py/main.py filter --software --format simple
    python py/main.py values                       # controlled vocabularies

Adding a step means writing ``py/<name>.py`` with a ``run()``, an
``add_arguments(parser)`` and a one-line docstring, then listing it in
``STEPS`` below.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

import transform
from transform import (
    DEFAULT_CSV, SIMPLE_COLUMNS, SOFTWARE_CATEGORIES, load, simplify, to_csv,
)

# Steps offered by the orchestrator, in the order they are listed.
STEPS = ["transform", "filter", "values"]

# Columns that carry a link or identifier. ``--has`` accepts any of these keys.
RESOURCE_COLUMNS = transform.LINK_COLUMNS

# Shorthands for common questions, resolved to one or more resource columns.
RESOURCE_ALIASES = {
    "code": transform.FORGE_COLUMNS,
    "repo": transform.FORGE_COLUMNS,
    "registry": list(transform.REGISTRY_COLUMNS),
    "doi": ["DOI"],
}

# Columns searched by ``--search``.
SEARCH_COLUMNS = ["item_name", "description", "notes"]

# Column order for the plain ``--format csv`` output.
OUTPUT_COLUMNS = [
    "id", "slug", "item_name", "category", "platform", "tags", "authors",
    "description", "DOI", "publication", "website",
    "github", "gitlab", "codeberg", "cran", "pypi",
]


# --------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------

def vocabulary(records: list[dict], field: str) -> dict[str, int]:
    """Return the observed values of ``field`` with their frequencies."""
    counts: dict[str, int] = {}
    for record in records:
        value = record.get(field, "")
        for item in (value if isinstance(value, list) else [value]):
            counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())))


def resolve(wanted: list[str], known: dict[str, int], field: str) -> set[str]:
    """Match user input against a controlled vocabulary, case-insensitively.

    Unknown values abort with a suggestion rather than silently returning an
    empty result -- the vocabularies are long and easy to mistype.
    """
    lookup = {value.lower(): value for value in known}
    resolved = set()
    for item in wanted:
        key = item.strip().lower()
        if key in lookup:
            resolved.add(lookup[key])
            continue
        close = difflib.get_close_matches(key, lookup, n=3, cutoff=0.4)
        hint = "; did you mean: " + ", ".join(lookup[c] for c in close) if close else ""
        sys.exit(f"error: unknown {field} {item!r}{hint}")
    return resolved


def has_resource(record: dict, keys: list[str]) -> bool:
    """True if the entry fills at least one of the requested resource columns."""
    columns: list[str] = []
    for key in keys:
        columns.extend(RESOURCE_ALIASES.get(key.lower(), [key]))
    return any(record.get(col) for col in columns)


def apply_filters(records: list[dict], args: argparse.Namespace) -> list[dict]:
    """Apply every requested filter; multiple filters are combined with AND."""
    result = records

    if args.category:
        wanted = resolve(args.category, vocabulary(records, "category"), "category")
        result = [r for r in result if r["category"] in wanted]

    if args.platform:
        wanted = resolve(args.platform, vocabulary(records, "platform"), "platform")
        result = [r for r in result if r["platform"] in wanted]

    if args.tag:
        wanted = resolve(args.tag, vocabulary(records, "tags"), "tag")
        if args.tags_all:  # entry must carry every requested tag
            result = [r for r in result if wanted <= set(r["tags"])]
        else:  # entry must carry at least one requested tag
            result = [r for r in result if wanted & set(r["tags"])]

    if args.has:
        result = [r for r in result if has_resource(r, args.has)]

    if args.search:
        pattern = re.compile(args.search, re.IGNORECASE)
        result = [
            r for r in result
            if any(pattern.search(r.get(col, "")) for col in SEARCH_COLUMNS)
        ]

    return result


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def flatten(record: dict) -> dict:
    """Reduce a record to the plain output columns, joining the list fields."""
    flat = {}
    for column in OUTPUT_COLUMNS:
        value = record.get(column, "")
        flat[column] = "|".join(value) if isinstance(value, list) else value
    return flat


def render(records: list[dict], fmt: str) -> str:
    """Serialise the filtered records in the requested format."""
    if fmt == "names":
        return "\n".join(r["item_name"] for r in records)

    if fmt == "ids":
        return "\n".join(f"{r['id']}\t{r['url']}" for r in records)

    if fmt == "simple":
        return to_csv([simplify(r) for r in records], SIMPLE_COLUMNS)

    if fmt == "json":
        import json
        return json.dumps(records, indent=2, ensure_ascii=False)

    if fmt == "jsonl":
        import json
        return "\n".join(json.dumps(r, ensure_ascii=False) for r in records)

    if fmt == "md":
        lines = []
        for record in records:
            meta = " / ".join(filter(None, [record["category"], record["platform"]]))
            lines.append(
                f"- **[{record['item_name']}]({record['url']})** "
                f"`{record['id']}` ({meta}) -- {record['description']}"
            )
        return "\n".join(lines)

    return to_csv([flatten(r) for r in records], OUTPUT_COLUMNS)


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------

def step_filter(args: argparse.Namespace) -> int:
    """Slice the dataset by type, platform, tag or text."""
    records = load(args.csv)
    if args.software:
        args.category = (args.category or []) + SOFTWARE_CATEGORIES

    selected = apply_filters(records, args)

    if args.count:
        print(len(selected))
        return 0

    output = render(selected, args.format)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
        print(f"{len(selected)} of {len(records)} entries -> {args.out}",
              file=sys.stderr)
    else:
        print(output)
    return 0


def step_values(args: argparse.Namespace) -> int:
    """List the controlled vocabularies of the dataset."""
    records = load(args.csv)
    for field, label in [("category", "category"), ("platform", "platform"),
                         ("tags", "tag")]:
        counts = vocabulary(records, field)
        print(f"\n== {label} ({len(counts)} values) ==")
        for value, count in counts.items():
            print(f"{count:5d}  {value or '(empty)'}")
    return 0


def step_transform(args: argparse.Namespace) -> int:
    """Write the table and its documentation to the output directory."""
    transform.run(args.csv, args.out_dir,
                  None if args.all_categories else SOFTWARE_CATEGORIES)
    return 0


def add_filter_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help="path to open-archaeo.csv (default: repository root)")
    parser.add_argument("--software", action="store_true",
                        help="shorthand for the three software categories: "
                             + ", ".join(SOFTWARE_CATEGORIES))
    parser.add_argument("--category", action="append", metavar="VALUE",
                        help="keep entries of this category; repeatable (OR)")
    parser.add_argument("--platform", action="append", metavar="VALUE",
                        help="keep entries on this platform; repeatable (OR)")
    parser.add_argument("--tag", action="append", metavar="VALUE",
                        help="keep entries carrying this tag; repeatable (OR)")
    parser.add_argument("--tags-all", action="store_true",
                        help="require all --tag values instead of any")
    parser.add_argument("--has", action="append", metavar="RESOURCE",
                        help="require a non-empty resource column, e.g. github, "
                             "pypi, DOI, or the shorthands code/registry")
    parser.add_argument("--search", metavar="REGEX",
                        help="case-insensitive regex over name, description, notes")
    parser.add_argument("--format",
                        choices=["csv", "simple", "json", "jsonl",
                                 "md", "names", "ids"],
                        default="csv",
                        help="output format; 'simple' is the collapsed "
                             "one-row-per-entry table written by the "
                             "transform step (default: csv)")
    parser.add_argument("--out", type=Path, metavar="FILE",
                        help="write to FILE instead of stdout")
    parser.add_argument("--count", action="store_true",
                        help="print only the number of matching entries")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Process the open-archaeo dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Controlled values may contain commas (e.g. 'Specifications, "
            "protocols and schemas'), so repeat the option instead of using\n"
            "comma-separated lists:\n"
            "  python py/main.py filter --category Scripts --category Products\n"
        ),
    )
    parser.add_argument("--list", action="store_true",
                        help="list the available steps and exit")
    subparsers = parser.add_subparsers(dest="step", metavar="STEP")

    transform_parser = subparsers.add_parser(
        "transform", help=step_transform.__doc__)
    transform.add_arguments(transform_parser)
    transform_parser.set_defaults(handler=step_transform)

    filter_parser = subparsers.add_parser("filter", help=step_filter.__doc__)
    add_filter_arguments(filter_parser)
    filter_parser.set_defaults(handler=step_filter)

    values_parser = subparsers.add_parser("values", help=step_values.__doc__)
    values_parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                               help="path to open-archaeo.csv")
    values_parser.set_defaults(handler=step_values)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        handlers = {"transform": step_transform, "filter": step_filter,
                    "values": step_values}
        print("Available steps:")
        for name in STEPS:
            print(f"  {name:<12} {handlers[name].__doc__}")
        return 0

    if not getattr(args, "handler", None):
        parser.print_help()
        return 1

    return args.handler(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:  # e.g. when piping into head
        sys.stderr.close()
        raise SystemExit(0)

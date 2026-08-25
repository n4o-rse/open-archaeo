#!/usr/bin/env python3
"""Entry point for the open-archaeo -> Wikidata route.

    python py/wikidata/main.py                 # check: verifies everything, writes nothing
    python py/wikidata/main.py reconcile       # what is in Wikidata already
    python py/wikidata/main.py vocab --suggest # resolve the controlled values
    python py/wikidata/main.py push            # dry run; --live to write
    python py/wikidata/main.py sparql          # build docs/sparql.html

``check`` is the default because the expensive way to discover that a property
changed datatype, or that a Q-id does not exist, is halfway through a batch of
edits. Everything except ``push --live`` is read-only.

Standard library only, like the rest of this package: reads go to the Wikidata
Query Service over urllib, writes to the Action API.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_DIR = HERE.parent          # py/
ROOT = PACKAGE_DIR.parent          # repository root
sys.path.insert(0, str(HERE))      # this folder, when run from elsewhere
sys.path.insert(0, str(PACKAGE_DIR))  # for transform.py

import check as check_step            # noqa: E402
import push as push_step              # noqa: E402
import reconcile as reconcile_step    # noqa: E402
import sparql as sparql_step          # noqa: E402
import vocabulary as vocabulary_step  # noqa: E402
from reconcile import CONCORDANCE_NAME  # noqa: E402
from transform import (                # noqa: E402
    DEFAULT_CSV, SOFTWARE_CATEGORIES, load, simplify, to_csv,
)

STEPS = ["check", "reconcile", "vocab", "push", "sparql"]

DEFAULT_OUT_DIR = ROOT / "out"
DEFAULT_CONFIG = HERE / "config.ini"
DEFAULT_VOCABULARY = HERE / "vocabulary.json"
DEFAULT_DOCS = HERE / "docs"


def slice_ids(path: Path | None) -> set[str] | None:
    """The ``id`` column of a slice file, or None when no slice was given.

    Two teams importing into the same Wikidata need to stay out of each other's
    rows, so every step that reads the source table can be narrowed to one
    slice. See out/OpenRefine/README.md and out/Python/README.md.
    """
    if path is None:
        return None
    if not path.is_file():
        sys.exit(f"error: slice file not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        ids = {row["id"] for row in csv.DictReader(handle) if row.get("id")}
    if not ids:
        sys.exit(f"error: no id column, or no rows, in {path}")
    return ids


def source_rows(args: argparse.Namespace) -> list[dict]:
    """The transformed table, filtered to the software subset by default."""
    records = load(args.csv)
    if not getattr(args, "all_categories", False):
        records = [r for r in records if r["category"] in set(SOFTWARE_CATEGORIES)]
    rows = [simplify(r) for r in records]
    wanted = slice_ids(getattr(args, "slice", None))
    if wanted is not None:
        rows = [r for r in rows if r["id"] in wanted]
        print(f"slice: {len(rows)} of {len(records)} entries", file=sys.stderr)
    return rows


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------

def step_check(args: argparse.Namespace) -> int:
    """Verify data, endpoints, identifiers, vocabulary and plan. Writes nothing."""
    return check_step.run(
        rows=source_rows(args),
        concordance_path=args.concordance or (args.out_dir / CONCORDANCE_NAME),
        vocabulary_path=args.vocabulary,
        config_path=args.config,
        offline=args.offline,
        do_login=args.login,
    )


def step_reconcile(args: argparse.Namespace) -> int:
    """Match entries against Wikidata and write the concordance."""
    rows = source_rows(args)
    print(f"reconciling {len(rows)} entries against Wikidata", file=sys.stderr)
    reconcile_step.reconcile(rows, use_registries=not args.no_registries)

    out = args.out or (args.out_dir / CONCORDANCE_NAME)
    if out.is_file() and not args.no_merge:
        rows = reconcile_step.merge_concordance(
            rows, reconcile_step.load_concordance(out))
    out.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0]) if rows else []
    out.write_text(to_csv(rows, columns) + "\n", encoding="utf-8")

    matched = sum(1 for r in rows if r["qid"])
    tagged = sum(1 for r in rows if r["is_chublet"] == "yes")
    print(f"{matched} of {len(rows)} matched, {tagged} already tagged -> {out}",
          file=sys.stderr)
    return 0


def step_vocab(args: argparse.Namespace) -> int:
    """Collect the controlled values that still need a Q-id."""
    vocab = vocabulary_step.scaffold(source_rows(args))
    if args.path.is_file():
        vocab = vocabulary_step.merge(vocab, vocabulary_step.load(args.path))
    if args.suggest:
        vocabulary_step.suggest(vocab)
    vocabulary_step.save(vocab, args.path)

    open_by_section = vocabulary_step.unresolved(vocab)
    total = sum(len(vocab[s]) for s in open_by_section)
    still_open = sum(len(v) for v in open_by_section.values())
    print(f"{total} controlled values, {still_open} still unresolved -> {args.path}",
          file=sys.stderr)
    return 0


def step_push(args: argparse.Namespace) -> int:
    """Write statements to Wikidata. Dry run unless --live."""
    concordance = args.concordance or (args.out_dir / CONCORDANCE_NAME)
    rows = reconcile_step.load_concordance(concordance)
    vocab = vocabulary_step.load(args.vocabulary)

    wanted = slice_ids(args.slice)
    if wanted is not None:
        rows = [r for r in rows if r["id"] in wanted]
        print(f"slice: {len(rows)} rows of the concordance", file=sys.stderr)

    plan_rows, skipped = push_step.plan(rows, vocab, only=args.only,
                                        limit=args.limit)
    if not plan_rows:
        print("nothing to do: no rows with a Q-id. Run 'reconcile' first, or "
              "add Q-ids to the concordance by hand.", file=sys.stderr)
        return 1

    total = sum(len(claims) for _, claims in plan_rows)
    print(f"{len(plan_rows)} items, {total} statements, {len(skipped)} values "
          "skipped", file=sys.stderr)

    if not args.live:
        push_step.show(plan_rows, skipped, show_skipped=args.show_skipped)
        print("\nDry run. Nothing was written. Re-run with --live to write.",
              file=sys.stderr)
        return 0

    return 1 if push_step.write(plan_rows, config_path=args.config,
                                mark_bot=args.mark_bot) else 0


def step_sparql(args: argparse.Namespace) -> int:
    """Build the query page and the .rq files from queries.py."""
    sparql_step.run(args.out_dir, do_verify=args.verify, strict=args.strict)
    return 0


# --------------------------------------------------------------------------
# Arguments
# --------------------------------------------------------------------------

def _add_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help="path to open-archaeo.csv (default: repository root)")
    parser.add_argument("--all-categories", action="store_true",
                        help="keep all 562 entries instead of the software subset")
    parser.add_argument("--slice", type=Path, metavar="FILE",
                        help="restrict to the ids listed in a slice CSV, "
                             "e.g. out/Python/open-archaeo-software.csv")


def _add_concordance(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="directory holding the concordance (default: out/)")
    parser.add_argument("--concordance", type=Path, metavar="FILE",
                        help=f"use FILE instead of <out-dir>/{CONCORDANCE_NAME}")


def add_check_arguments(parser: argparse.ArgumentParser) -> None:
    _add_source(parser)
    _add_concordance(parser)
    parser.add_argument("--vocabulary", type=Path, default=DEFAULT_VOCABULARY,
                        help="vocabulary file to inspect")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="credentials file (default: py/wikidata/config.ini)")
    parser.add_argument("--offline", action="store_true",
                        help="skip every network check; data and plan only")
    parser.add_argument("--login", action="store_true",
                        help="also authenticate and report the account's rights. "
                             "Obtains a token, makes no edit")


def add_reconcile_arguments(parser: argparse.ArgumentParser) -> None:
    _add_source(parser)
    _add_concordance(parser)
    parser.add_argument("--out", type=Path, metavar="FILE",
                        help="write the concordance to FILE")
    parser.add_argument("--no-registries", action="store_true",
                        help="skip the CRAN and PyPI lookups")
    parser.add_argument("--no-merge", action="store_true",
                        help="discard manually curated Q-ids from a previous run")


def add_vocab_arguments(parser: argparse.ArgumentParser) -> None:
    _add_source(parser)
    parser.add_argument("--path", type=Path, default=DEFAULT_VOCABULARY,
                        help="vocabulary file to create or update")
    parser.add_argument("--suggest", action="store_true",
                        help="print Wikidata search hits for unresolved values. "
                             "Never writes a Q-id")


def add_push_arguments(parser: argparse.ArgumentParser) -> None:
    _add_concordance(parser)
    parser.add_argument("--vocabulary", type=Path, default=DEFAULT_VOCABULARY,
                        help="vocabulary mapping controlled values to Q-ids")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="credentials file (default: py/wikidata/config.ini)")
    parser.add_argument("--live", action="store_true",
                        help="actually write. Without this nothing leaves the machine")
    parser.add_argument("--limit", type=int, default=0, metavar="N",
                        help="only the first N items (0 = all)")
    parser.add_argument("--only", action="append", metavar="ID",
                        help="only this open-archaeo id or Q-id; repeatable")
    parser.add_argument("--mark-bot", action="store_true",
                        help="set the bot flag (requires the bot right)")
    parser.add_argument("--show-skipped", type=int, default=20, metavar="N",
                        help="how many skipped values to list in a dry run")
    parser.add_argument("--slice", type=Path, metavar="FILE",
                        help="restrict to the ids listed in a slice CSV")


def add_sparql_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_DOCS,
                        help="where to write the page (default: py/wikidata/docs/)")
    parser.add_argument("--verify", action="store_true",
                        help="run every query against WDQS before writing")
    parser.add_argument("--strict", action="store_true",
                        help="with --verify, fail the build on a failing query")


HANDLERS = {
    "check": (add_check_arguments, step_check),
    "reconcile": (add_reconcile_arguments, step_reconcile),
    "vocab": (add_vocab_arguments, step_vocab),
    "push": (add_push_arguments, step_push),
    "sparql": (add_sparql_arguments, step_sparql),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import open-archaeo into Wikidata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="With no step, 'check' runs: it verifies the whole route and "
               "writes nothing.\n")
    parser.add_argument("--list", action="store_true",
                        help="list the available steps and exit")
    subparsers = parser.add_subparsers(dest="step", metavar="STEP")
    for name in STEPS:
        adder, handler = HANDLERS[name]
        sub = subparsers.add_parser(name, help=handler.__doc__)
        adder(sub)
        sub.set_defaults(handler=handler)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    if "--list" in argv:
        print("Available steps:")
        for name in STEPS:
            print(f"  {name:<12} {HANDLERS[name][1].__doc__}")
        return 0

    # No step given: run the one that cannot do any damage.
    if not argv or argv[0].startswith("-"):
        argv = ["check", *argv]

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:  # e.g. when piping into head
        sys.stderr.close()
        raise SystemExit(0)

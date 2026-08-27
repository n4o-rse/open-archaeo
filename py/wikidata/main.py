#!/usr/bin/env python3
"""Entry point for the open-archaeo -> Wikidata route.

    python py/wikidata/main.py all             # the whole read-only route, then open the preview
    python py/wikidata/main.py                 # check: verifies everything, writes nothing
    python py/wikidata/main.py preview         # docs/preview.html: what would be written
    python py/wikidata/main.py reconcile       # what is in Wikidata already
    python py/wikidata/main.py vocab --suggest # resolve the controlled values
    python py/wikidata/main.py subjects        # the P921 worksheet
    python py/wikidata/main.py push            # dry run; --live to write
    python py/wikidata/main.py sparql          # build docs/sparql.html
    python py/wikidata/main.py site            # build docs/index.html

``check`` is the default because the expensive way to discover that a property
changed datatype, or that a Q-id does not exist, is halfway through a batch of
edits. Everything except ``push --live`` is read-only.

Every step works on ``out/Python/open-archaeo-software.csv`` by default -- the
half of the dataset this team owns during the hackathon. ``--slice`` points
somewhere else and ``--full`` uses all 416 entries.

Standard library only, like the rest of this package: reads go to the Wikidata
Query Service over urllib, writes to the Action API.
"""

from __future__ import annotations

import argparse
import csv
import sys
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_DIR = HERE.parent          # py/
ROOT = PACKAGE_DIR.parent          # repository root
sys.path.insert(0, str(HERE))      # this folder, when run from elsewhere
sys.path.insert(0, str(PACKAGE_DIR))  # for transform.py

from api import WikidataError          # noqa: E402
import categories as categories_step  # noqa: E402
import check as check_step            # noqa: E402
import labels as label_cache          # noqa: E402
import preview as preview_step        # noqa: E402
import push as push_step              # noqa: E402
import reconcile as reconcile_step    # noqa: E402
# 'site' is a standard-library module name, so the module is 'landing'.
import landing as landing_step        # noqa: E402
import sparql as sparql_step          # noqa: E402
import subjects as subjects_step      # noqa: E402
import vocabulary as vocabulary_step  # noqa: E402
from reconcile import CONCORDANCE_NAME  # noqa: E402
import split as split_step            # noqa: E402
import transform as transform_step    # noqa: E402
from transform import (                # noqa: E402
    DEFAULT_CSV, SOFTWARE_CATEGORIES, load, simplify, to_csv,
)

STEPS = ["all", "check", "preview", "reconcile", "vocab", "categories",
         "subjects", "push", "sparql", "site"]

# What ``all`` runs, in order, and whether the step needs a connection.
#
# Two steps are deliberately absent. ``push`` at any setting, because writing to
# Wikidata is a decision and a step named "all" is a bad place to keep one. And
# ``reconcile``, because it is the slow one: 208 entries mean several rounds of
# batched queries against a query service that answers when it answers, and its
# result -- the concordance -- changes far less often than the pages built from
# it. ``--reconcile`` puts it back in.
ALL_STEPS = [
    ("transform", False, "rebuild out/ from open-archaeo.csv"),
    ("vocab", False, "collect the controlled values"),
    ("categories", False, "build the P31 class worksheet"),
    ("subjects", False, "build the P921 worksheet"),
    ("check", True, "verify the whole route"),
    ("preview", False, "render every item, with labels"),
    ("sparql", False, "build the query page"),
    ("site", False, "build the landing page"),
]

# Where ``reconcile`` goes when it is asked for: before check, so that the plan
# section has a concordance to report on.
RECONCILE_STEP = ("reconcile", True, "look up what Wikidata has already")

DEFAULT_OUT_DIR = ROOT / "out"
# The half of the dataset this team owns. See out/Python/README.md.
DEFAULT_SLICE = ROOT / "out" / "Python" / "open-archaeo-software.csv"
DEFAULT_CONFIG = HERE / "config.ini"
DEFAULT_VOCABULARY = HERE / "vocabulary.json"
DEFAULT_DOCS = ROOT / "docs"


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
    wanted = None if getattr(args, "full", False) else \
        slice_ids(getattr(args, "slice", None))
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


def step_preview(args: argparse.Namespace) -> int:
    """Render what would be written, as a page that looks like Wikidata."""
    preview_step.run(
        slice_path=args.slice,
        vocabulary=vocabulary_step.load(args.vocabulary),
        concordance=args.concordance or (args.out_dir / CONCORDANCE_NAME),
        output=args.out,
        size=args.size,
        with_labels=args.labels,
    )
    return 0


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
    if args.set:
        vocabulary_step.resolve(vocab, args.set)
    if args.suggest:
        vocabulary_step.suggest(vocab)
    vocabulary_step.save(vocab, args.path)

    open_by_section = vocabulary_step.unresolved(vocab)
    total = sum(len(vocab[s]) for s in open_by_section)
    still_open = sum(len(v) for v in open_by_section.values())
    print(f"{total} controlled values, {still_open} still unresolved -> {args.path}",
          file=sys.stderr)
    return 0


def step_subjects(args: argparse.Namespace) -> int:
    """Build the P921 reconciliation worksheet, or read a filled one back."""
    if args.apply:
        subjects_step.apply_worksheet(args.out, args.vocabulary)
        return 0
    # Deliberately not sliced. The subject vocabulary is shared between the two
    # teams, so a worksheet covering half the data would produce half a
    # vocabulary and two different Q-ids for the same term.
    records = load(args.csv)
    software = [simplify(r) for r in records
                if r["category"] in set(SOFTWARE_CATEGORIES)]
    everything = [simplify(r) for r in records]
    subjects_step.run(software, output=args.out, tags_md=args.tags_md,
                      suggest=args.suggest, all_rows=everything)
    return 0


def step_categories(args: argparse.Namespace) -> int:
    """Build the P31 class worksheet, or read a filled one back."""
    if args.verify:
        return 1 if categories_step.verify_worksheet(
            categories_step.read_worksheet(args.out)) else 0
    if args.apply:
        categories_step.apply_worksheet(args.out, args.vocabulary)
        return 0
    # Deliberately not sliced and not limited to the software subset: the
    # categories belong to open-archaeo as a whole, and deciding them together
    # keeps one term from acquiring two Q-ids.
    records = load(args.csv)
    software = [simplify(r) for r in records
                if r["category"] in set(SOFTWARE_CATEGORIES)]
    everything = [simplify(r) for r in records]
    categories_step.run(software, output=args.out, suggest=args.suggest,
                        all_rows=everything)
    return 0


def step_push(args: argparse.Namespace) -> int:
    """Write statements to Wikidata. Dry run unless --live."""
    concordance = args.concordance or (args.out_dir / CONCORDANCE_NAME)
    vocab = vocabulary_step.load(args.vocabulary)

    if args.create and not concordance.is_file():
        # Creating is the one mode that works without a concordance, and it has
        # to: an entry with no Q-id anywhere is exactly what it is for, and
        # requiring 'reconcile' first would make the slow step a precondition of
        # the step that does not need it. The rows come from the table instead,
        # with the concordance columns empty, and the file is written when the
        # items exist.
        print(f"no concordance at {concordance} -- creating from the table; "
              "every entry counts as not yet in Wikidata", file=sys.stderr)
        rows = source_rows(args)
        for row in rows:
            row.update({key: "" for key in reconcile_step.CONCORDANCE_EXTRA})
        return _create_items(args, rows, vocab)

    rows = reconcile_step.load_concordance(concordance)

    wanted = None if args.full else slice_ids(args.slice)
    if wanted is not None:
        rows = [r for r in rows if r["id"] in wanted]
        print(f"slice: {len(rows)} rows of the concordance", file=sys.stderr)

    if args.create:
        return _create_items(args, rows, vocab)

    plan_rows, issues = push_step.plan(rows, vocab, only=args.only,
                                       limit=args.limit)
    if not plan_rows:
        print("nothing to do: no rows with a Q-id. Run 'reconcile' first, or "
              "add Q-ids to the concordance by hand.", file=sys.stderr)
        return 1

    total = sum(len(claims) for _, claims in plan_rows)
    blocked = sum(1 for _, issue in issues if issue.severity == "blocked")
    print(f"{len(plan_rows)} items, {total} statements, {len(issues)} issues "
          f"({blocked} blocked)", file=sys.stderr)

    if not args.live:
        push_step.show(plan_rows, issues, show_skipped=args.show_skipped)
        print("\nDry run. Nothing was written. Re-run with --live to write.",
              file=sys.stderr)
        return 0

    return 1 if push_step.write(plan_rows, config_path=args.config,
                                mark_bot=args.mark_bot) else 0


def _create_items(args: argparse.Namespace, rows: list[dict],
                  vocab: dict) -> int:
    """push --create: make an item for every row that has no Q-id.

    The concordance is rewritten afterwards, always -- a created item whose
    Q-id is not recorded is a duplicate waiting to be made on the next run.
    """
    creations, issues = push_step.plan_creations(
        rows, vocab, only=args.only, limit=args.limit)
    if not creations:
        print("nothing to create: every row already has a Q-id.",
              file=sys.stderr)
        return 0

    stopped = push_step.blocking(issues)
    blocked_ids = {row["id"] for row, _ in stopped}
    print(f"{len(creations)} items to create, "
          f"{sum(len(c) for _, c, _ in creations)} statements, "
          f"{len(stopped)} blocked on {len(blocked_ids)} items", file=sys.stderr)

    if args.skip_blocked and blocked_ids:
        # One ambiguous forge should not hold up two hundred sound items, so
        # the gate can be made per-item instead of per-batch. The skipped ones
        # are named rather than counted: they are work, not noise.
        names = [f"{r['id']} {r['name']}" for r, _, _ in creations
                 if r["id"] in blocked_ids]
        creations = [c for c in creations if c[0]["id"] not in blocked_ids]
        issues = [(row, issue) for row, issue in issues
                  if row["id"] not in blocked_ids]
        stopped = []
        print(f"  --skip-blocked: leaving out {len(names)} item(s): "
              + "; ".join(names[:5])
              + (" …" if len(names) > 5 else ""), file=sys.stderr)
        if not creations:
            print("nothing left to create.", file=sys.stderr)
            return 1

    if not args.live:
        push_step.show_creations(creations, issues,
                                 show_skipped=args.show_skipped)
        print("\nDry run. Nothing was created. Re-run with --live to create.",
              file=sys.stderr)
        return 0

    if stopped:
        codes = sorted({issue.code for _, issue in stopped})
        sys.exit("error: refusing to create while blocked issues stand: "
                 + ", ".join(codes)
                 + f" ({len(blocked_ids)} item(s)).\n"
                   "An item created wrong has to be found again before it can "
                   "be fixed. Either resolve the cause -- 'vocab --suggest' "
                   "and 'vocab --set' for a missing Q-id, 'categories --apply' "
                   "for a class -- or pass --skip-blocked to create the sound "
                   "items and leave these for later.")

    unchecked = [r for r, _, _ in creations if not r.get("checked")]
    if unchecked:
        print(f"warning: {len(unchecked)} of these have never been reconciled. "
              "Every one that already exists in Wikidata becomes a duplicate "
              "somebody has to merge.", file=sys.stderr)

    created, failed = push_step.create(creations, config_path=args.config,
                                       mark_bot=args.mark_bot)
    concordance = args.concordance or (args.out_dir / CONCORDANCE_NAME)
    columns = list(rows[0]) if rows else []
    concordance.write_text(to_csv(rows, columns) + "\n", encoding="utf-8")
    print(f"{created} created, {failed} failed -> {concordance}",
          file=sys.stderr)
    return 1 if failed else 0


def step_site(args: argparse.Namespace) -> int:
    """Write docs/index.html, the landing page for GitHub Pages."""
    landing_step.run(args.out_dir)
    return 0


def step_sparql(args: argparse.Namespace) -> int:
    """Build the query page and the .rq files from queries.py."""
    sparql_step.run(args.out_dir, do_verify=args.verify, strict=args.strict)
    return 0


def step_all(args: argparse.Namespace) -> int:
    """Run the whole read-only route in order, then open the preview.

    One command for the session described at the end of the README: rebuild the
    table, collect the controlled values, look up what Wikidata already has,
    verify, render, publish the pages. Every step in it is read-only -- push is
    deliberately absent, because writing is a decision and a step called "all"
    is the wrong place to make it.

    A failing step stops the run, except the two that need a connection: with
    --offline, or when the network is simply not there, they are skipped and
    the rest still produces a page.
    """
    steps = list(ALL_STEPS)
    if args.reconcile:
        steps.insert(steps.index(("check", True, "verify the whole route")),
                     RECONCILE_STEP)
    steps = [s for s in steps if not (args.offline and s[1])]
    print(f"running {len(steps)} steps" + (" (offline)" if args.offline else ""),
          file=sys.stderr)

    for index, (name, online, why) in enumerate(steps, start=1):
        print(f"\n== {index}/{len(steps)}  {name} -- {why} ==", file=sys.stderr)
        try:
            code = _run_sub(name, args)
        except WikidataError as error:
            # Only the steps that need Wikidata can raise this, and a query
            # service that is slow or down is not a reason to abandon the run:
            # everything after this point builds from what is on disk.
            print(f"   {name}: {error}", file=sys.stderr)
            print("   carrying on without it.", file=sys.stderr)
            continue
        if code:
            if online:
                print(f"   {name} failed; carrying on without it. The preview "
                      "will be built from what is on disk.", file=sys.stderr)
                continue
            print(f"   {name} failed. Stopping.", file=sys.stderr)
            return code

    page = args.out or preview_step.DEFAULT_OUTPUT
    if not page.is_file():
        print(f"\nno page at {page}", file=sys.stderr)
        return 1
    print(f"\n{page}", file=sys.stderr)
    if args.open:
        webbrowser.open(page.resolve().as_uri())
    return 0


def _run_sub(name: str, args: argparse.Namespace) -> int:
    """Run one step of ``all`` with its own defaults plus the flags that carry.

    Each step is re-parsed from its own subparser rather than handed this
    namespace: a step that grows an option keeps working, and a step that does
    not have --slice does not suddenly acquire one.
    """
    if name == "transform":
        transform_step.run(args.csv, args.out_dir,
                           None if args.all_categories else SOFTWARE_CATEGORIES)
        split_step.run(args.out_dir / transform_step.OUTPUT_NAME, args.out_dir,
                       quiet=True)
        return 0

    argv = [name]
    if args.all_categories and name in ("vocab", "subjects", "reconcile", "check"):
        argv.append("--all-categories")
    if args.full and name in ("vocab", "reconcile", "check"):
        argv.append("--full")
    if args.slice and name in ("vocab", "reconcile", "check"):
        argv += ["--slice", str(args.slice)]
    if name == "preview":
        # preview has no --full: it previews whatever table it is pointed at,
        # so --full means pointing it at the whole one.
        table = (args.out_dir / transform_step.OUTPUT_NAME) if args.full \
            else args.slice
        if table:
            argv += ["--slice", str(table)]
        argv += ["--out", str(args.out or preview_step.DEFAULT_OUTPUT)]
        if not args.offline:
            argv.append("--labels")
    if name == "check" and args.offline:
        argv.append("--offline")

    sub = build_parser().parse_args(argv)
    return sub.handler(sub)


# --------------------------------------------------------------------------
# Arguments
# --------------------------------------------------------------------------

def _add_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help="path to open-archaeo.csv (default: repository root)")
    parser.add_argument("--all-categories", action="store_true",
                        help="keep all 562 entries instead of the software subset")
    parser.add_argument("--slice", type=Path, default=DEFAULT_SLICE,
                        metavar="FILE",
                        help="slice CSV whose ids to work on "
                             "(default: out/Python/open-archaeo-software.csv)")
    parser.add_argument("--full", action="store_true",
                        help="ignore the slice and use all 416 entries")


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


def add_preview_arguments(parser: argparse.ArgumentParser) -> None:
    _add_concordance(parser)
    parser.add_argument("--slice", type=Path, default=DEFAULT_SLICE,
                        metavar="FILE",
                        help="slice CSV to preview "
                             "(default: out/Python/open-archaeo-software.csv)")
    parser.add_argument("--vocabulary", type=Path, default=DEFAULT_VOCABULARY,
                        help="vocabulary mapping controlled values to Q-ids")
    preview_step.add_arguments(parser)


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
    parser.add_argument("--set", action="append", nargs=3, default=[],
                        metavar=("SECTION", "VALUE", "QID"),
                        help="resolve one controlled value, e.g. "
                             "--set version_control_system Git Q186055. "
                             "Repeatable")
    parser.add_argument("--suggest", action="store_true",
                        help="print Wikidata search hits for unresolved values. "
                             "Never writes a Q-id")


def add_subjects_arguments(parser: argparse.ArgumentParser) -> None:
    # No --slice here: see step_subjects.
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help="path to open-archaeo.csv")
    parser.add_argument("--vocabulary", type=Path, default=DEFAULT_VOCABULARY,
                        help="vocabulary file that --apply writes into")
    subjects_step.add_arguments(parser)


def add_push_arguments(parser: argparse.ArgumentParser) -> None:
    _add_concordance(parser)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help="path to open-archaeo.csv, read by --create when "
                             "there is no concordance yet")
    parser.add_argument("--all-categories", action="store_true",
                        help="keep all 562 entries instead of the software subset")
    parser.add_argument("--vocabulary", type=Path, default=DEFAULT_VOCABULARY,
                        help="vocabulary mapping controlled values to Q-ids")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="credentials file (default: py/wikidata/config.ini)")
    parser.add_argument("--live", action="store_true",
                        help="actually write. Without this nothing leaves the machine")
    parser.add_argument("--skip-blocked", action="store_true",
                        help="with --create, leave out the items that carry a "
                             "blocked issue and create the rest, instead of "
                             "refusing the whole batch")
    parser.add_argument("--create", action="store_true",
                        help="create an item for every row that has no Q-id, "
                             "instead of adding statements to matched ones. "
                             "Refuses while any other blocked issue stands")
    parser.add_argument("--limit", type=int, default=0, metavar="N",
                        help="only the first N items (0 = all)")
    parser.add_argument("--only", action="append", metavar="ID",
                        help="only this open-archaeo id or Q-id; repeatable")
    parser.add_argument("--mark-bot", action="store_true",
                        help="set the bot flag (requires the bot right)")
    parser.add_argument("--show-skipped", type=int, default=20, metavar="N",
                        help="how many skipped values to list in a dry run")
    parser.add_argument("--slice", type=Path, default=DEFAULT_SLICE,
                        metavar="FILE",
                        help="slice CSV whose ids to work on "
                             "(default: out/Python/open-archaeo-software.csv)")
    parser.add_argument("--full", action="store_true",
                        help="ignore the slice and use all 416 entries")


def add_categories_arguments(parser: argparse.ArgumentParser) -> None:
    # No --slice and no --full: see step_categories.
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help="path to open-archaeo.csv")
    parser.add_argument("--vocabulary", type=Path, default=DEFAULT_VOCABULARY,
                        help="vocabulary file that --apply writes into")
    categories_step.add_arguments(parser)


def add_sparql_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_DOCS,
                        help="where to write the page (default: docs/)")
    parser.add_argument("--verify", action="store_true",
                        help="run every query against WDQS before writing")
    parser.add_argument("--strict", action="store_true",
                        help="with --verify, fail the build on a failing query")


def add_all_arguments(parser: argparse.ArgumentParser) -> None:
    _add_source(parser)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="directory for the table and the concordance "
                             "(default: out/)")
    parser.add_argument("--out", type=Path, metavar="FILE",
                        help="where to write the preview "
                             "(default: docs/preview.html)")
    parser.add_argument("--reconcile", action="store_true",
                        help="also run reconcile, which is left out because it "
                             "is slow and its result changes rarely")
    parser.add_argument("--offline", action="store_true",
                        help="skip every step that needs a connection. Labels "
                             "come from the cache")
    parser.add_argument("--no-open", dest="open", action="store_false",
                        help="build everything but do not open a browser")


HANDLERS = {
    "all": (add_all_arguments, step_all),
    "check": (add_check_arguments, step_check),
    "preview": (add_preview_arguments, step_preview),
    "reconcile": (add_reconcile_arguments, step_reconcile),
    "vocab": (add_vocab_arguments, step_vocab),
    "categories": (add_categories_arguments, step_categories),
    "subjects": (add_subjects_arguments, step_subjects),
    "push": (add_push_arguments, step_push),
    "sparql": (add_sparql_arguments, step_sparql),
    "site": (landing_step.add_arguments, step_site),
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
            summary = (HANDLERS[name][1].__doc__ or "").strip().splitlines()[0]
            print(f"  {name:<12} {summary}")
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

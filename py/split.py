#!/usr/bin/env python3
"""Split the software table into two slices of equal shape for parallel work.

Two teams importing the same 416 entries into Wikidata need halves that are
alike, not merely equal in size. A random split leaves one team with every CRAN
package and the other with none, and then each finds a different set of
problems -- which is exactly what a shared hackathon is trying to avoid.

So the split is stratified: entries are grouped by the features that change how
they have to be modelled, and each group is dealt out alternately. Both slices
therefore carry roughly half of every category, half the registry entries, half
the DOIs, half the archived snapshots, and half the awkward multi-repository
rows.

    python py/main.py split          # write out/OpenRefine/ and out/Python/

The result is deterministic: the same input gives the same two files, so a
slice can be regenerated rather than passed around.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "out" / "open-archaeo-software.csv"
OUTPUT_NAME = "open-archaeo-software.csv"

# One slice per team. The folder name is the tool; the file inside keeps the
# name of the table it came from, so the two are interchangeable.
SLICES = ("OpenRefine", "Python")

# The features that change how an entry has to be modelled. Two entries with
# the same signature need the same treatment, so they are the unit that gets
# dealt out alternately.
def signature(row: dict) -> tuple:
    return (
        row["category"],
        row["platform_role"],
        bool(row["registry"]),
        bool(row["doi"]),
        bool(row["internetarchive"]),
        bool(row["website"]),
        row["repository"].count("|"),
    )


def split(rows: list[dict]) -> dict[str, list[dict]]:
    """Deal the rows out alternately within each stratum.

    The counter runs across strata rather than restarting inside each one.
    Restarting would hand the first row of every stratum to the same slice, and
    with many small strata that bias accumulates.
    """
    ordered = sorted(rows, key=lambda r: (signature(r), r["id"]))
    slices: dict[str, list[dict]] = {name: [] for name in SLICES}
    for index, row in enumerate(ordered):
        slices[SLICES[index % len(SLICES)]].append(row)
    for rows_in_slice in slices.values():
        rows_in_slice.sort(key=lambda r: r["name"].lower())
    return slices


def balance_report(slices: dict[str, list[dict]]) -> list[str]:
    """One line per feature, showing how evenly it landed."""
    features = {
        "entries": lambda r: True,
        "Packages and libraries": lambda r: r["category"] == "Packages and libraries",
        "Standalone software": lambda r: r["category"] == "Standalone software",
        "Scripts": lambda r: r["category"] == "Scripts",
        "with repository": lambda r: bool(r["repository"]),
        "with registry": lambda r: bool(r["registry"]),
        "with DOI": lambda r: bool(r["doi"]),
        "with publication": lambda r: bool(r["publication"]),
        "with website": lambda r: bool(r["website"]),
        "with archive snapshot": lambda r: bool(r["internetarchive"]),
        "language given": lambda r: r["platform_role"] == "language",
        "host application": lambda r: r["platform_role"] == "host application",
        "several repositories": lambda r: "|" in r["repository"],
    }
    width = max(len(name) for name in features)
    lines = [f"{'':<{width}}  " + "  ".join(f"{name:>10}" for name in SLICES)]
    for name, test in features.items():
        counts = [sum(1 for row in slices[s] if test(row)) for s in SLICES]
        lines.append(f"{name:<{width}}  " + "  ".join(f"{c:>10}" for c in counts))
    return lines


def read_source(path: Path) -> tuple[list[dict], list[str]]:
    if not path.is_file():
        sys.exit(f"error: {path} not found. Run 'python py/main.py transform' first.")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_slice(rows: list[dict], columns: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run(source: Path = DEFAULT_SOURCE, out_dir: Path | None = None,
        *, quiet: bool = False) -> dict[str, Path]:
    """Write both slices and return where they went."""
    rows, columns = read_source(source)
    out_dir = out_dir or source.parent
    slices = split(rows)

    written = {}
    for name, rows_in_slice in slices.items():
        path = out_dir / name / OUTPUT_NAME
        write_slice(rows_in_slice, columns, path)
        written[name] = path

    if not quiet:
        for line in balance_report(slices):
            print(line, file=sys.stderr)
        overlap = set(r["id"] for r in slices[SLICES[0]]) & \
            set(r["id"] for r in slices[SLICES[1]])
        print(f"\noverlap between the slices: {len(overlap)}", file=sys.stderr)
        for name, path in written.items():
            print(f"{len(slices[name]):3d} entries -> {path}", file=sys.stderr)
    return written


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help="table to split (default: out/open-archaeo-software.csv)")
    parser.add_argument("--out-dir", type=Path,
                        help="where the slice folders go (default: next to the source)")
    parser.add_argument("--quiet", action="store_true",
                        help="do not print the balance report")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_arguments(parser)
    args = parser.parse_args(argv)
    run(args.source, args.out_dir, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

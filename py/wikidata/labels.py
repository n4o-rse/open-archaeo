#!/usr/bin/env python3
"""English labels for the Q-ids this import uses, cached on disk.

Properties read as words in the preview because ``PROPERTY_LABELS`` in
``model.py`` spells them out; items did not, because there is no such list --
the Q-ids come from the identity block, from ``vocabulary.json`` and from the
concordance, and what they are called is Wikidata's business, not this
package's.

So instead of a hand-written table, this module keeps a cache: ``labels.json``
next to ``vocabulary.json``, filled by any step that talks to Wikidata anyway,
read by every step that does not. After one online run the preview shows names
even with no network at all, and a label that changes on Wikidata is one
``--labels`` away from being right again.

Nothing here invents a label. A Q-id that has never been looked up renders as
itself, which is the honest thing for a page whose whole purpose is to show
what would be written.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent / "labels.json"

NOTE = ("Generated cache: English labels for the Q-ids this import touches. "
        "Refreshed by 'check' and by 'preview --labels'. Safe to delete.")


def load(path: Path = DEFAULT_PATH) -> dict[str, str]:
    """The cache, or an empty mapping when there is none yet."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"  ignoring unreadable label cache {path}: {error}",
              file=sys.stderr)
        return {}
    return {k: v for k, v in data.get("labels", {}).items() if v}


def save(labels: dict[str, str], path: Path = DEFAULT_PATH) -> None:
    """Write the cache, sorted, so a rebuild produces no spurious diff."""
    if not labels:
        return
    payload = {"_note": NOTE, "labels": dict(sorted(labels.items()))}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def update(new: dict[str, str], path: Path = DEFAULT_PATH) -> dict[str, str]:
    """Merge freshly read labels into the cache and return the whole of it.

    New values win: the point of a refresh is to pick up a rename.
    """
    merged = {**load(path), **{k: v for k, v in new.items() if v}}
    save(merged, path)
    return merged


def resolve(qids, *, path: Path = DEFAULT_PATH, fetch: bool = False) -> dict[str, str]:
    """Labels for ``qids``: from the cache, and from Wikidata when asked.

    ``fetch=False`` never touches the network, so the preview stays usable on
    a train. ``fetch=True`` reads every id and refreshes the cache, including
    the ones already in it.
    """
    wanted = set(qids)
    cached = load(path)
    if not fetch:
        return {q: cached[q] for q in wanted if q in cached}

    from api import WikidataError, get_entities  # local: keeps this offline-safe

    try:
        entities = get_entities(sorted(wanted), props="labels")
    except WikidataError as error:
        print(f"  could not read labels ({error}); using the cache",
              file=sys.stderr)
        return {q: cached[q] for q in wanted if q in cached}

    fresh = {qid: entity.get("labels", {}).get("en", {}).get("value", "")
             for qid, entity in entities.items() if "id" in entity}
    merged = update(fresh, path)
    return {q: merged[q] for q in wanted if q in merged}

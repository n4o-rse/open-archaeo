# The Python slice

208 of the 416 software entries in open-archaeo, to be modelled and uploaded to
Wikidata through the Action API with the code in `py/wikidata/`. The other 208
are in `../OpenRefine/`, going in through OpenRefine. Neither slice overlaps
the other, so the two teams can work at the same time without editing the same
items.

Regenerate with `python py/main.py split`; the split is deterministic, so the
same file comes back. It is stratified rather than random: both slices carry
roughly half of every category, half the registry entries, half the DOIs, half
the archived snapshots. That is deliberate -- a random split would leave one
team with every CRAN package and neither team seeing the whole shape of the
problem.

The mapping itself is documented once, in `py/wikidata/docs/MAPPING.md`, and
every step and flag in `py/wikidata/README.md`. This file is about working on
this slice in particular.

## Before anything else

Two statements go on **every** item, whatever else is known about it:

| Property | Value |
|---|---|
| `P31` instance of | `Q141115627` |
| `P6104` maintained by WikiProject | `Q141169143` |

The class alone would also catch research software modelled by other
communities. `P6104` is what draws the boundary and makes the set retrievable
as a set, which is how both teams will check each other's progress.

## This file is the default

Every step in `py/wikidata/` reads **this** file unless told otherwise. No flag
to remember, no way for the two teams to collide by accident:

```bash
python py/wikidata/main.py preview     # works on out/Python/ already
```

`--slice FILE` points elsewhere and `--full` uses all 416 entries. Defaulting
rather than requiring a flag is deliberate: forgetting `--slice` on
`push --live` is the one mistake in this workflow that is awkward to undo, and
a default cannot be forgotten.

## Look before you write

```bash
python py/wikidata/main.py preview
```

Writes `py/wikidata/docs/preview.html` -- **all 208** of your entries with the
statements they would produce, laid out the way Wikidata lays out statements.
Open it in a browser. It is the test of the mapping, which is why it shows
everything rather than a sample.

The filter bar gets you to the interesting part: by category, by whether the
item has problems, by a specific issue code, or by free text. The issue table
at the top is clickable -- each row filters the page down to the items that
raised it.

### The three boxes under each item

| Box | Meaning |
|---|---|
| **Blocked**, red | The import would produce something *wrong or invalid*: a statement missing a required qualifier, an unresolved class, or an item with no Q-id at all. Close these before writing. |
| **Deferred**, amber | A value exists in open-archaeo and is deliberately not written here -- it belongs on a different statement, or the Q-id it needs has not been chosen yet. Nothing is wrong; something is waiting. |
| **Notes**, grey | A remark to see once: a description that still reads as a sentence, for instance. |

Filtering to **with blocked issues** is the worklist for the day. Filtering to
**with no issues** is the set that is genuinely ready.

Before `reconcile` runs, every item shows a red `not-reconciled` -- honest, and
a good picture of how much matching is left. Run it after, and the page ends
with a ready-to-copy command for the first three items that are reconciled
*and* carry nothing blocked.

## The session

```bash
python py/wikidata/main.py --offline        # does the data still transform?
python py/wikidata/main.py preview          # look at the shape of the statements
python py/wikidata/main.py                  # do the identifiers hold on Wikidata?
python py/wikidata/main.py reconcile        # what is already in Wikidata?
python py/wikidata/main.py preview --labels # look again, now with values resolved
python py/wikidata/main.py push             # the dry run, as text
python py/wikidata/main.py push --only <id> --only <id> --only <id> --live
python py/wikidata/main.py push --live      # the rest, once those three look right
```

The preview page ends with exactly that three-item command, filled in with the
first three reconciled ids, so it can be copied rather than assembled. Three is
the right size for a batch you intend to open on Wikidata afterwards and read.

`check` is the default step and writes nothing anywhere. It verifies that the
two obligatory Q-ids exist, that every property still has the datatype the
model assumes, and that no two entries claim the same Q-id. Run it before and
after `reconcile`: before it tells you the route works, after it tells you what
`push` would actually do.

A dry run is the default for `push` and `--live` is the only way past it.

## The vocabulary comes from the other team

`P277` programmed in, `P1547` depends on software and `P921` main subject take
*items* as values, and the CSV gives strings. Reconciling those is what
OpenRefine is good at, so **that slice owns the vocabulary for both halves**.
They will hand over a two-column CSV of value and Q-id; it goes into
`py/wikidata/vocabulary.json`.

Until it arrives, `push` skips those statements rather than guessing -- an
invented Q-id is a wrong statement that looks like a right one -- and lists
every skipped value at the end of the dry run. So the sensible order for the
day is: reconcile and push everything that does not need the vocabulary, then
fill it in and run `push` again. Re-running is safe, because statements that
already exist are skipped.

If you need to unblock yourself before the handover, `oa vocab --suggest`
prints Wikidata search hits for each unresolved value. It never writes a Q-id;
choosing is still a person's job, and choosing differently from the other team
is how one dataset becomes two vocabularies.

## What the code will not do for you

**It never creates items.** Deciding that a tool is missing from Wikidata is a
judgement call, and one worth making in front of the search results rather than
in a batch of 208. Only rows that `reconcile` matched to a Q-id are touched;
everything else waits for a person. If you decide an item should exist, create
it by hand and write the Q-id into `out/open-archaeo-concordance.csv` with
`match_property` set to `manual` -- a Q-id entered that way survives the next
`reconcile` run.

**It will not assert a Zenodo DOI.** 24 of the 34 DOIs begin `10.5281`, which
is Zenodo. A Zenodo DOI is a *deposit* DOI: it identifies a release, not the
tool, so it belongs on `P348` and is simply wrong at item level. These are
reported in the dry run, not silently dropped.

**It will not attach a mismatched archive snapshot.** Fourteen entries across
the full dataset list a repository on one forge and a snapshot of another --
the tool moved, the crawl did not follow. The snapshot is paired to the
repository on the path, not on position, and unpaired snapshots are reported.

**It will not match on names.** `name` is not unique in open-archaeo, so
matching on it would manufacture false positives at exactly the rate the
duplicates occur. Reconciliation uses repository URL, then DOI, then CRAN, then
PyPI -- in that order, and stops at the first hit.

## Credentials

Copy `py/wikidata/config.example.ini` to `py/wikidata/config.ini` and fill in a
**bot password** from Special:BotPasswords, not your ordinary one. The file is
git-ignored; check that before you put a password in it. `WIKIDATA_USERNAME`
and `WIKIDATA_PASSWORD` in the environment override it, which is the better
option on a shared machine.

Set a real User-Agent with a contact address. `push` refuses to start while it
still carries the placeholder, because Wikidata's User-Agent policy expects one
and an anonymous batch is the kind of thing that gets an IP blocked mid-event.

`oa --login` authenticates, reports whether the account may edit and whether it
has the bot right, and obtains a CSRF token -- without making a single edit.
Worth running once at the start of the day.

## Checking your work

Open `py/wikidata/docs/sparql.html` in a browser -- it queries Wikidata live
and is shared with the other team. Three of its queries are worklists rather
than reports:

- entries with a repository but no licence (open-archaeo records none at all,
  so this one will be long),
- repository statements missing the required `P8423` qualifier -- anything here
  is a bug in the import, since the value is derivable from the forge,
- items carrying only one of the two obligatory statements, which usually means
  an interrupted run.

For those three, an empty result is the healthy one. The first query,
*Everything currently tagged*, is the shared scoreboard: it counts both slices
together, because `P6104` does not care which tool wrote it.

## Handing back

`out/open-archaeo-concordance.csv` already holds `id` and `qid` for this slice.
The other team will export the same two columns for theirs. Merged, the two
give a concordance for the whole 416 without either team re-querying what the
other already established.

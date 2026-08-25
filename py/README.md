# Processing open-archaeo

Python steps that turn `open-archaeo.csv` (562 entries) into machine-readable
tables, on the way to Wikidata and chublets.software. Standard library only --
no installation beyond Python 3.9+.

`py/main.py` is the single entry point; each step is a module beside it that
also runs standalone.

```bash
python py/main.py                                     # transform, then split
python py/main.py --list                              # available steps
python py/main.py transform                           # write out/*.csv
python py/main.py split                               # two slices for parallel work
python py/main.py filter --software --format simple   # ad-hoc slicing
python py/main.py values                              # controlled vocabularies

python py/wikidata/main.py                            # the Wikidata route

python py/transform.py --out-dir out/                 # same step, standalone
```

Adding a step means writing `py/<name>.py` with a `run()`, an
`add_arguments(parser)` and a one-line docstring, then listing it in `STEPS`
in `main.py`.

## The software subset

`--software` is a shorthand for the three categories describing software
rather than documentation or data collections: Packages and libraries,
Standalone software, Scripts. That is **416 of 562 entries**. The remaining
146 would need a different Wikidata class anyway.

`transform.py` writes this subset by default; `--all-categories` keeps all 562.

## Output

`transform.py` writes a single table, `out/open-archaeo-software.csv`, and a
generated `out/README.md` documenting it column by column, with fill counts
computed from the rows actually written so the documentation cannot drift away
from the data.

One table rather than two. An earlier draft also emitted a long
one-row-per-URL table carrying a `wikidata_property` column, but that property
is a function of the *column*, not of the row -- `P1324` appeared 360 times
unchanged. It belongs in the schema documentation, which is where it now
lives: in the `Property` column of `out/README.md` and in the audit below. The
long form is a `melt` away for whoever needs it, and would fit naturally as
its own step if a QuickStatements export is ever wanted.

Twenty-two source columns become twenty-two output columns, one of which
(`platform_role`) is derived rather than carried over. The transformation is
lossless: every non-empty source value reappears, only reshaped, checked by
comparing each output row against its raw counterpart.

Within the software subset only one entry (`nervia`) has two repository URLs,
and none has both a CRAN and a PyPI page, so in practice those columns are
single-valued.

Run without a step, `main.py` does the usual thing: `transform`, then `split`.
That is the whole preparation of the dataset, and it is what you want after
pulling a new `open-archaeo.csv`. Both steps only write into `out/`, and the
split is deterministic, so running it again is harmless.

`split` writes `out/OpenRefine/` and `out/Python/`: two halves of the software
table, stratified so that each carries roughly half of every category, half the
registry entries, half the DOIs and half the archived snapshots. Each folder
has a README of its own explaining how to model that slice with the tool it is
named after. The two do not overlap, so both can be imported at the same time.

## The Wikidata route

Everything to do with the Wikidata import lives in `py/wikidata/`, with its own
entry point and its own README:

```bash
python py/wikidata/main.py            # check: verifies the route, writes nothing
python py/wikidata/main.py preview    # docs/preview.html: the mapping, item by item
python py/wikidata/main.py --list     # the seven steps
```

Eight steps -- `check`, `preview`, `reconcile`, `vocab`, `subjects`, `push`,
`sparql`, `site` -- producing a concordance of what is already in Wikidata, a registry of
the controlled values, the writes themselves, and the pages in `docs/`. Only
`push --live` writes anything to Wikidata, and it needs that flag explicitly.

Every step works on `out/Python/open-archaeo-software.csv` by default -- the
half of the dataset this team owns. `--slice FILE` points elsewhere, `--full`
uses all 416 entries.

See `py/wikidata/README.md` for the flags, `docs/MAPPING.md` for the mapping
itself, and `docs/ENRICHMENT.md` for what the CSV cannot supply.

### What ends up in `docs/`

`docs/` is a small generated site, not documentation kept by hand:

| File | Made by | What it is |
|---|---|---|
| `index.html` | `main.py site` | Landing page linking the rest. |
| `preview.html` | `main.py preview` | Every entry with the statements it would produce, and every problem the mapping raises. Filterable by category, severity and issue code. |
| `sparql.html`, `queries/*.rq` | `main.py sparql` | Eight live queries against the Wikidata Query Service. |
| `MAPPING.md` | by hand | Which column becomes which statement, and why. |
| `ENRICHMENT.md` | by hand | What the columns cannot give, and which source can. |

**Publishing.** GitHub Pages in this repository is currently driven by
`.github/workflows/hugo.yml`, which uploads Hugo's `./public`. A repository-root
`docs/` is therefore *not* served as things stand. Two ways round it:

- Set Pages to **deploy from a branch**, folder `/docs`, in the repository
  settings. Simplest, and it retires the Hugo deployment.
- Keep Hugo and build into its static directory instead:
  `python py/wikidata/main.py preview --out static/preview.html`, which Hugo
  copies verbatim to `<baseurl>/preview.html`.

Locally, `python -m http.server` inside `docs/` works for both pages. Opening
`sparql.html` over `file://` does not, because the browser blocks the request
to the query service; `preview.html` opens fine either way.

At 208 items `preview.html` is around a megabyte. Fine in a browser, awkward in
a diff -- worth deciding deliberately whether it belongs in version control.

### The problems the preview reports

`preview.html` groups everything the mapping could not do into three boxes, and
the difference between them is the point:

| Severity | Colour | Means |
|---|---|---|
| `blocked` | red | The import would produce something **wrong or invalid** -- a violated required-qualifier constraint, an unresolved class, an item with no Q-id. Close before writing. |
| `deferred` | amber | A value exists and is deliberately not written here: it belongs on another statement, or the Q-id it needs has not been chosen. Nothing wrong; something waiting. |
| `note` | grey | A remark to see once, such as a description that still reads as a sentence. |

The same codes appear in `check` and in the `push` dry run, so the three views
agree. They are defined once, in `ISSUE_LEGEND` in `py/wikidata/model.py`.

## Is everything usable already in the file?

Everything the source contains is in the file, and that has been verified. But
*present* and *statement-ready* are not the same thing. Three groups.

### Ready to map

| Column | Property | Note |
|---|---|---|
| `repository` | `P1324` source code repository URL | Verified. `repository_host` can drive the `P8423` version control system qualifier -- Git for GitHub, GitLab and Codeberg; Launchpad is Bazaar; Bitbucket is ambiguous. |
| `website` | `P856` official website | Verified. |
| `doi` | `P356` DOI | Verified. |
| `registry` | `P5565` CRAN project, `P5568` PyPI project | The package name sits in the URL, so an external identifier rather than a link. |
| `url` | `P2888` exact match | The open-archaeo entry is a record *of* the tool, not a page mentioning it. |
| `blogpost`, `youtube` | `P973` described at URL | Pages that describe without being the same thing. |
| `internetarchive` | `P1065` archive URL | Normally a *qualifier* on `P1324` rather than a statement of its own. |
| `name` | item label | Direct. |

### Needs a decision or a lookup first

| Column | Obstacle |
|---|---|
| `category` | Maps to a second `P31` value, but the target class is a choice. The three categories are seeded in `vocabulary.json` as `item_class`, each `null` until someone decides; an unresolved one shows as a **blocked** issue on the preview rather than as a quietly thinner item. |
| `platform` | Conflates three things, which is why `platform_role` exists. `language` (301 entries) maps to `P277` programmed in; `host application` (34) to `P1547` depends on software; `deployment` (8, `Mobile app` and `Web app`) is not a platform statement at all but a refinement of `P31`. Each target still needs its own item. |
| `tags` | Maps to `P921` main subject, but the 56 terms have to be reconciled one by one. `python py/wikidata/main.py subjects` writes a worksheet for that, carrying each term's scope note from `tags.md` -- and marks the six that are not subjects at all. |
| `authors` | 502 mentions, 283 distinct; 221 look like forge usernames rather than personal names, and **187 are demonstrably the owner of a forge URL in the same dataset**. So `P2037` GitHub username reconciles to a person or organisation item, where matching a display string reconciles to nothing. `P178` developer is therefore tractable and currently not emitted -- it is reported as `unresolved-author` so the gap stays visible. |
| `description` | Wikidata descriptions are short, lower case and carry no terminal punctuation; these are sentences, 348 of them ending in a full stop and 413 beginning with a capital. Usable, but only after rewriting. |

### Not in open-archaeo at all

These have to come from the repositories, the registries or Software Heritage:

- **Copyright licence (`P275`).** `P1324` carries a constraint that items
  should state a licence, and open-archaeo records none. This is the largest
  single gap.
- **Inception (`P571`)** and **software version (`P348`)**.
- **Programming language for the 73 entries with an empty `platform`.** Not
  recoverable from the text either: a dozen language patterns tested against
  every field of those rows returned exactly one hit. The descriptions say what
  a tool does, not what it is written in.
- **Software Heritage identifier (`P6138`).** Upstream lists this as a planned
  addition in `ToDo.md`, so it may arrive without any work on this side.

`docs/ENRICHMENT.md` works through where each of these actually lives -- the
GitHub API for licence, inception and archived status, CRAN `DESCRIPTION` for
the 39 packages, Zenodo for the 24 deposits -- and the order worth doing them
in. The short version: the columns are close to mined out, and what remains is
behind the URLs they contain rather than inside them.

`twitter` and `notes` are in the file for losslessness and are not import
material: the former is empty throughout the subset, the latter describes the
dataset rather than the tools.

### Reconcile before creating anything

Many of these tools are already in Wikidata, partly from earlier Little
Minions work. The repository URL is the strongest join key:

```sparql
SELECT ?item ?itemLabel ?repo WHERE {
  VALUES ?repo { <https://github.com/ISAAKiel/quantAAR> }
  ?item wdt:P1324 ?repo .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

Feed the `repository` column into the `VALUES` block, or reconcile the
simplified CSV in OpenRefine against `P1324` and `P356`.

## Identifiers

The dataset has no identifier column and `item_name` is not unique
(`harris-matrix` occurs twice, `roman-amphitheaters` and `dayofarchaeology`
once more). `transform.py` mints three fields:

| Field | Example |
|---|---|
| `slug` | `archaeological-catalogue-from-csv-spreadsheet` |
| `url` | `https://open-archaeo.info/post/archaeological-catalogue-from-csv-spreadsheet/` |
| `id` | `f1159e` |

### slug

Ported from `clean_slug()` and `unique_slug()` in `R/site.R`, so it matches
what the site actually publishes -- including the upstream quirks: only a
trailing `.r` is stripped, and entries sharing a slug all get their first
author appended (`harris-matrix-tsdye`, `harris-matrix-semerj`).

Grouping for that disambiguation runs over **all 562 entries**, never over a
filtered subset. Filtering first would change which names collide and produce
slugs that no longer resolve.

Hugo then sanitises the filename once more, which the R code does not
anticipate: characters outside its allowed set are dropped. Verified against
the live site --

```
item_name   Fiche Stratigraphique Numérique (FSN)
R slug      fiche-stratigraphique-numérique-(fsn)
published   fiche-stratigraphique-numérique-fsn
url         …/post/fiche-stratigraphique-num%C3%A9rique-fsn/
```

The brackets vanish, the accent survives and is percent-encoded only in the
URL. Four entries are affected (`é`, brackets, apostrophe, `!`); all four
reproduce the live URLs exactly.

### id

`sha256(slug)` truncated to six hexadecimal characters -- deterministic, no
counter or registry needed. No collisions across the 562 entries; six
characters give 16.7M values, and `mint_ids()` aborts loudly rather than
emitting a duplicate, so raising `ID_LENGTH` is a one-line fix if the dataset
grows.

**Worth deciding before this reaches Wikidata:** the id is a function of the
slug, so it is a convenient handle, not a persistent identifier. Rename an
entry, or add a second entry whose name collides and forces an author suffix,
and the id of an *existing* record changes. If chublets needs identifiers that
survive upstream edits, they have to be minted once and stored, not derived.

### url

Whether every URL resolves is worth checking: the live site currently reports
246 packages, 87 standalone and 32 guides where this snapshot has 248, 94 and
33, so the fork's CSV runs ahead of the deployed build.

## `filter` options

| Option | Effect |
|---|---|
| `--software` | Shorthand for the three software categories. |
| `--category VALUE` | Keep entries of this category; repeatable (OR). |
| `--platform VALUE` | Keep entries on this platform; repeatable (OR). |
| `--tag VALUE` | Keep entries carrying this tag; repeatable (OR). |
| `--tags-all` | Require *all* `--tag` values instead of any. |
| `--has RESOURCE` | Require a non-empty column: `github`, `pypi`, `cran`, `DOI`, `website`, … or the shorthands `code` (any forge) and `registry` (CRAN or PyPI). |
| `--search REGEX` | Case-insensitive regular expression over name, description and notes. |
| `--format` | `csv` (default), `simple`, `json`, `jsonl`, `md`, `names`, `ids`. |
| `--out FILE` | Write to a file instead of standard output. |
| `--count` | Print only the number of matches. |
| `--csv PATH` | Read a different copy of the dataset. |

Controlled values may contain commas (`Specifications, protocols and
schemas`), so options are repeated rather than comma-separated. A misspelt
value aborts with a suggestion instead of silently returning nothing.

```bash
# Python tools with a public repository, as a linked Markdown list
python py/main.py filter --platform Python --has code --format md

# id and resolvable URL, one pair per line
python py/main.py filter --software --format ids

# citable entries
python py/main.py filter --has DOI --count

# chronology across two tags (OR)
python py/main.py filter --tag "Chronological modelling" \
  --tag "Radiocarbon dating, calibration and sequencing" --format names
```

## Types in the dataset

Three orthogonal notions, combined with AND:

| Field | Meaning | Cardinality | Values |
|---|---|---|---|
| `category` | What kind of thing an entry is | Exactly one | 7 |
| `platform` | Technical environment | Zero or one | 23, empty for 215 |
| `tag1`–`tag5` | Thematic subject | Zero to five | 59 |

| Category | Entries |
|---|---|
| Packages and libraries | 248 |
| Standalone software | 94 |
| Lists and datasets | 84 |
| Scripts | 74 |
| Guides | 33 |
| Products | 15 |
| Specifications, protocols and schemas | 14 |

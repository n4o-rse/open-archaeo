# open-archaeo → Wikidata

Everything to do with the Wikidata import lives in this folder. `py/` above it
stays what it was: reshaping `open-archaeo.csv` into `out/open-archaeo-software.csv`.

Standard library only, like the rest of the package -- no `requests`, no
`pywikibot`. Reads go to the Wikidata Query Service over `urllib`, writes to
the Action API.

```
check      →  nothing                                verify the whole route
preview    →  docs/preview.html                      every item, as Wikidata shows it, with its problems
reconcile  →  out/open-archaeo-concordance.csv       what already exists
vocab      →  vocabulary.json                        what the controlled values mean
push       →  Wikidata                               write, dry run by default
sparql     →  docs/sparql.html                       queries that check the result
```

## The slice

Every step works on `out/Python/open-archaeo-software.csv` by default -- the
half of the dataset this team owns during the hackathon, produced by
`python py/main.py`. `--slice FILE` points somewhere else, `--full` uses all
416 entries.

Defaulting to the slice rather than requiring a flag is deliberate: forgetting
`--slice` on `push --live` is the one mistake in this workflow that is awkward
to undo, and a default cannot be forgotten.

## Start here

```bash
python py/wikidata/main.py
```

With no step, `check` runs, and `check` writes nothing anywhere. That is the
default on purpose: the expensive way to discover that a property changed
datatype, or that a Q-id does not exist, is halfway through a batch of edits.
It walks the whole route -- data, endpoints, identifiers, concordance,
vocabulary, credentials, and the plan itself -- and reports each line as `ok`,
`warn` or `FAIL`.

Failures set the exit code. Warnings do not, because most of them describe work
that is simply not done yet: no concordance, unresolved vocabulary, no
credentials. A first run is expected to be all warnings.

What `check` actually verifies against Wikidata:

- The two obligatory Q-ids exist, and it prints their labels so you can see
  they are what you meant.
- Every property the model uses exists **and still has the datatype the model
  assumes**. A `P1324` that stopped being a url would otherwise fail one row at
  a time.
- Duplicate Q-ids in the concordance -- two entries claiming the same item is a
  reconciliation error, and the only check here that fails rather than warns.

## Files

| File | What it is |
|---|---|
| `main.py` | The entry point. Nothing else is meant to be run directly except `sparql.py`. |
| `preview.py` | Renders the planned statements as a Wikidata-looking page. |
| `model.py` | Which identifiers are used and how a row becomes statements. Change the mapping here, nowhere else. |
| `api.py` | HTTP, the query service, and the Action API client. |
| `reconcile.py` | Matching and the concordance. |
| `vocabulary.py` | The controlled-value registry. |
| `push.py` | Planning and writing. |
| `check.py` | The preflight. |
| `queries.py` | The example queries, as source. |
| `sparql.py` | Renders the query page from them. |
| `vocabulary.json` | Generated: the registry itself, mostly `null` until filled in. |
| `config.example.ini` | Copy to `config.ini`. Only `push --live` reads it. |
| `docs/MAPPING.md` | Why each column maps where it does. |
| `docs/sparql.html` | Generated: the query page. |
| `docs/preview.html` | Generated: the preview of what would be written. |

`model.py` and `docs/MAPPING.md` are the same statement twice, once executable
and once in prose. If you change one, change the other.

## Steps and flags

### `check`

Verifies everything and writes nothing.

| Flag | Effect |
|---|---|
| `--offline` | Skip every network check. Data and plan only -- useful on a train, and the only mode that works without a connection. |
| `--login` | Also authenticate and report the account's rights. Obtains a CSRF token; **makes no edit**. |
| `--csv PATH` | Read a different copy of `open-archaeo.csv`. |
| `--all-categories` | Check all 562 entries instead of the 416-entry software subset. |
| `--concordance FILE` | Inspect a concordance elsewhere. |
| `--out-dir DIR` | Directory holding the concordance (default `out/`). |
| `--vocabulary FILE` | Inspect a different vocabulary file. |
| `--config FILE` | Credentials file to report on (default `py/wikidata/config.ini`). |

### `preview`

```bash
python py/wikidata/main.py preview            # all items in the slice
python py/wikidata/main.py preview --size 25  # one per modelling case, then fill
python py/wikidata/main.py preview --labels   # resolve Q-ids to labels
```

Writes `docs/preview.html`: every entry in the slice with the statements it
would produce, rendered the way Wikidata displays them -- property label and
number on the left, value on the right, qualifiers indented under the statement
they belong to.

It shows the whole set rather than a sample, because it is a test of the
mapping and a mapping is tested against all of the data. The filter bar is how
you get to the interesting part: by category, by whether the item has problems,
by a specific issue code, or by free text. The issue table in the header is
clickable -- each row filters the page down to the items that raised it.

**The three boxes under each item are the point of the page.** They answer the
question "what does *not written* mean", which the text dry run leaves vague:

| Box | Meaning |
|---|---|
| **Blocked**, red | The import would produce something *wrong or invalid*: a statement violating a required-qualifier constraint, an unresolved class, or an item with no Q-id at all. Gaps to close before writing. |
| **Deferred**, amber | A value exists in open-archaeo and is deliberately not written here -- it belongs on a different statement, or the Q-id it needs has not been chosen. Nothing is wrong; something is waiting. |
| **Notes**, grey | A remark a reviewer should see once: a description that still reads as a sentence, for instance. |

Every issue carries a code, so the same taxonomy appears in `check`, in the
`push` dry run and on this page. The codes and what each means live in
`ISSUE_LEGEND` in `model.py`.

An issue that fires on *every* item is a remark about the mapping rather than
about any item, so it goes in the header instead -- that is where the two
modelling decisions below are explained.

| Flag | Effect |
|---|---|
| `--size N` | Show only N items, one per modelling case first. Default 0, meaning all. |
| `--labels` | Read English labels for the Q-ids used. Read-only; without it the page contacts nothing. |
| `--out FILE` | Write somewhere else. |
| `--slice FILE`, `--concordance FILE`, `--out-dir DIR`, `--vocabulary FILE` | As above. |

Run before `reconcile` and every item carries a red `not-reconciled`: honest,
and a good picture of how much reconciliation is left. Run after, and the page
ends with a ready command for the first three items that are reconciled *and*
carry nothing blocked.

At 208 items the page is around a megabyte. That is fine in a browser and
awkward in a diff, so it is worth leaving out of version control.

### `reconcile`

Writes `out/open-archaeo-concordance.csv`: the transformed table plus six
columns saying whether the entry is in Wikidata and how it was found.

| Column | Content |
|---|---|
| `qid` | The matched item, or empty. |
| `match_property` | `P1324`, `P356`, `P5565`, `P5568`, or `manual`. |
| `match_value` | The exact value that matched, so a wrong match is visible. |
| `wikidata_label` | The item's label, for eyeballing false positives. |
| `is_chublet` | Whether it already carries **both** obligatory statements. |
| `checked` | Date of the lookup. |

Four keys are tried, in decreasing order of confidence: repository URL, DOI,
CRAN package, PyPI package. Repository URLs are queried in several spellings,
because Wikidata holds whatever the editor pasted -- with and without a
trailing slash, with and without `.git`, occasionally over http.

**Names are deliberately not a key.** `item_name` is not unique in open-archaeo
-- that is why `unique_slug()` exists -- so matching on it would manufacture
false positives at exactly the rate the duplicates occur.

| Flag | Effect |
|---|---|
| `--out FILE` | Write the concordance somewhere else. |
| `--out-dir DIR` | Directory for the concordance (default `out/`). |
| `--no-registries` | Skip the CRAN and PyPI lookups. |
| `--no-merge` | Discard manually curated Q-ids from a previous run. |
| `--csv PATH`, `--all-categories` | As above. |

Anything entered by hand survives a rebuild: a `qid` whose `match_property` is
empty or `manual` is treated as a curation decision and carried over.

### `vocab`

`P277`, `P1547`, `P921` and the `P8423` qualifier take *items* as values, and
open-archaeo gives strings. `vocabulary.json` is the registry that maps one to
the other: 79 values across five sections, each `null` until someone fills it in.

| Flag | Effect |
|---|---|
| `--suggest` | Print Wikidata search hits for every unresolved value. **Never writes a Q-id.** |
| `--path FILE` | Create or update a different vocabulary file. |
| `--csv PATH`, `--all-categories` | As above. |

Label search is a good way to find a candidate and a bad way to choose one, so
the choice stays with a person. `push` skips a statement whose value is
unresolved rather than guessing: an invented Q-id is a wrong statement that
looks like a right one.

### `push`

| Flag | Effect |
|---|---|
| `--live` | **Actually write.** Without it nothing leaves the machine. |
| `--limit N` | Only the first N items. |
| `--only ID` | Only this open-archaeo id or Q-id. Repeatable. |
| `--mark-bot` | Set the bot flag. Requires the bot right -- `check --login` reports whether the account has it. |
| `--show-skipped N` | How many skipped values to list in a dry run (default 20). |
| `--concordance FILE`, `--out-dir DIR`, `--vocabulary FILE`, `--config FILE` | As above. |

A dry run is the default and `--live` is the only way past it. This writes to
the live Wikidata, not to a private Wikibase: use a bot password, put a real
User-Agent with a contact address in `config.ini`, and read the bot policy
before doing more than a handful of items at a time. `push` refuses to start
while the User-Agent still carries its placeholder.

Only rows that already have a `qid` are touched. **The step never creates
items** -- deciding that a tool is missing from Wikidata is a judgement call,
and one worth making in front of the search results rather than in a batch of
416. Statements that already exist are skipped, so re-running is safe.

Two things it will not assert:

- **A Zenodo DOI.** `10.5281/…` is a *deposit* DOI: it identifies a release, so
  it belongs on `P348` and would be wrong at item level.
- **A mismatched archive snapshot.** Fourteen entries list a Codeberg
  repository and a GitHub snapshot -- the tool moved, the crawl did not follow.
  Pairing them by position would claim the Internet Archive holds a copy it
  never saw, so the pairing is made on the snapshot path instead.

### `sparql`

| Flag | Effect |
|---|---|
| `--out-dir DIR` | Where to write (default `py/wikidata/docs/`). |
| `--verify` | Run every query against WDQS before writing. |
| `--strict` | With `--verify`, fail the build on a failing query. |

`queries.py` is the source; the step writes `docs/sparql.html` and
`docs/queries/*.rq` from it, so the two cannot drift apart. Eight queries, of
which three are worklists rather than reports -- entries with a repository but
no licence, repository statements missing the required `P8423` qualifier, and
items carrying only one of the two obligatory statements. For those, an empty
result is the healthy one.

Two deviations from the query pages in the `wdt-*` repositories, both
deliberate:

- **A live endpoint, not Pyodide.** Those pages parse a static Turtle file in
  the browser so an archived copy stays queryable with no service to keep
  alive. Here the graph *is* Wikidata, so there is nothing to ship. The cost is
  real: the page needs `query.wikidata.org` to be up, and a query typed into it
  leaves the machine.
- **`queries.py`, not `queries.yaml`.** A YAML file would mean a parser
  dependency for one list of strings, and this package installs nothing.

**Publishing.** GitHub Pages in this repository is driven by the Hugo workflow
in `.github/workflows/hugo.yml`, so a `docs/` folder is not served. To publish
through that pipeline, build into Hugo's static directory instead --
`python py/wikidata/main.py sparql --out-dir static` -- and Hugo copies it
verbatim to `<baseurl>/sparql.html`. Locally, `python -m http.server` inside
`docs/` works; opening the file over `file://` does not, because the browser
blocks the request to the endpoint.

## Two modelling decisions

**Exact match rather than described at URL.** The open-archaeo entry is not a
page that mentions the tool; it is a record *of* the tool. `P2888` exact match
carries that reading -- its `equivalent property` is `skos:exactMatch` and
`schema:sameAs`, and its unique-value constraint matches the one-entry-one-item
relation. `P973` described at URL is then free for blog posts and videos, which
describe a tool without being the same thing as it.

In current Wikidata practice `P2888` is used mostly for ontology alignment, so
a registry record is a slightly unusual value for it. The semantics fit; the
company it keeps is different. `P973` remains the fallback and loses only the
"same thing" assertion. Better than both would be a dedicated open-archaeo
identifier property on the `P6830` swMATH precedent.

**Classification beyond the chublet class.** The chublet class and the
WikiProject go on every item and neither says what *kind* of software it is.
`P31` therefore takes further values: one per open-archaeo category, plus any
superclass meant for all of them. Both are `vocabulary.json` entries starting
at `null`, so an unresolved category shows as a blocked issue rather than as a
quietly thinner item.

If the chublet class is already a `P279` subclass of that superclass, stating
both is redundant for a query written `wdt:P31/wdt:P279*`. Whether to state it
anyway is a judgement about how the data will be queried, which is why it is a
vocabulary entry rather than a hard-coded statement.

## A first session

```bash
python py/wikidata/main.py --offline        # does the data still transform?
python py/wikidata/main.py preview          # every item and every problem, in a browser
python py/wikidata/main.py                  # do the identifiers still hold?
python py/wikidata/main.py reconcile        # what is in Wikidata already?
python py/wikidata/main.py vocab --suggest  # find candidates, choose by hand
python py/wikidata/main.py preview --labels # look again: now with Q-ids resolved
python py/wikidata/main.py push             # the dry run, as text
python py/wikidata/main.py push --only <id> --only <id> --only <id> --live
python py/wikidata/main.py sparql           # publish the queries that check it
```

Steps two and six are the ones worth slowing down on, and they are the same
step twice: once before the data is reconciled, to check the shape of the
statements, and once after, to check the values. The page ends with the command
for the first three ready items, which is the right size for a batch you intend
to open in a browser afterwards.

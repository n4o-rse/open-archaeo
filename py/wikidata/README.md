# open-archaeo → Wikidata

Everything to do with the Wikidata import lives in this folder. `py/` above it
stays what it was: reshaping `open-archaeo.csv` into `out/open-archaeo-software.csv`.

Standard library only, like the rest of the package -- no `requests`, no
`pywikibot`. Reads go to the Wikidata Query Service over `urllib`, writes to
the Action API.

```
check      →  nothing                                verify the whole route
reconcile  →  out/open-archaeo-concordance.csv       what already exists
vocab      →  vocabulary.json                        what the controlled values mean
push       →  Wikidata                               write, dry run by default
sparql     →  docs/sparql.html                       queries that check the result
```

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

## A first session

```bash
python py/wikidata/main.py --offline        # does the data still transform?
python py/wikidata/main.py                  # do the identifiers still hold?
python py/wikidata/main.py reconcile        # what is in Wikidata already?
python py/wikidata/main.py vocab --suggest  # find candidates, choose by hand
python py/wikidata/main.py                  # check again: the plan is now real
python py/wikidata/main.py push             # read the dry run carefully
python py/wikidata/main.py push --limit 3 --live   # three items, then look at them
python py/wikidata/main.py sparql           # publish the queries that check it
```

Step six is the one worth slowing down on. The dry run prints every statement
it would make, and everything it declined to make and why.

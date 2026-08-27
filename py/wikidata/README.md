# open-archaeo → Wikidata

Everything to do with the Wikidata import lives in this folder. `py/` above it
stays what it was: reshaping `open-archaeo.csv` into `out/open-archaeo-software.csv`.

Standard library only, like the rest of the package -- no `requests`, no
`pywikibot`. Reads go to the Wikidata Query Service over `urllib`, writes to
the Action API.

```
all        →  everything below, then a browser        one command for a whole session
check      →  nothing                                verify the whole route
preview    →  docs/preview.html                      every item, as Wikidata shows it, with its problems
site       →  docs/index.html                        the landing page that links them
reconcile  →  out/open-archaeo-concordance.csv       what already exists
vocab      →  vocabulary.json                        what the controlled values mean
subjects   →  out/tag-reconciliation.csv             the P921 worksheet, with scope notes
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
python py/wikidata/main.py all
```

`all` runs the read-only route in order -- rebuild the table, collect the
controlled values, build the subject worksheet, check, preview, publish the
query and landing pages -- and then opens `docs/preview.html` in a browser.

Two steps are left out. `push`, at any setting: writing to Wikidata is a
decision, and a step named *all* is the wrong place to keep one. And
`reconcile`, because it is the slow one -- several rounds of batched queries
against a service that answers when it answers -- while its result, the
concordance, changes far less often than the pages built from it. `--reconcile`
puts it back in, before `check`, so the plan has a concordance to report on.

A step that needs Wikidata and does not get an answer is reported and skipped;
the run carries on, because everything after it builds from what is on disk.

| Flag | Effect |
|---|---|
| `--reconcile` | Also run `reconcile`. |
| `--offline` | Skip every step that needs a connection. The preview is still built, with whatever labels are already cached. |
| `--no-open` | Build everything, open nothing. |
| `--full` | Use all 416 entries instead of the slice, preview included. |
| `--out FILE` | Write the preview somewhere other than `docs/preview.html`. |
| `--out-dir DIR`, `--csv PATH`, `--slice FILE`, `--all-categories` | As for the individual steps. |

A step that fails for any other reason stops the run.

## One step at a time

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

- Every Q-id in the identity block exists, and it prints their labels so you
  can see they are what you meant.
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
| `subjects.py` | The P921 worksheet, and reading a filled one back. |
| `push.py` | Planning and writing. |
| `check.py` | The preflight. |
| `queries.py` | The example queries, as source. |
| `sparql.py` | Renders the query page from them. |
| `labels.py` | The Q-id label cache: read offline, refreshed by anything that talks to Wikidata. |
| `vocabulary.json` | Generated: the registry itself, mostly `null` until filled in. |
| `labels.json` | Generated: English labels for the Q-ids used, so the preview reads as words offline. |
| `config.example.ini` | Copy to `config.ini`. Only `push --live` reads it. |

| `landing.py` | Writes `docs/index.html`. Named `landing` because `site` is a standard-library module. |

`model.py` and `docs/MAPPING.md` are the same statement twice, once executable
and once in prose. If you change one, change the other.

## Steps and flags

### `all`

Runs the steps below in order and opens the preview. See *Start here* above for
its flags.

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

Item values read as words in the same way, out of `labels.json`. That cache is
filled by any step that contacts Wikidata anyway -- `check` reads the identity
block's labels to report them, and keeps them -- so after one online run the
page names its Q-ids even when built with no connection at all. A Q-id that has
never been looked up renders as itself: nothing here invents a label for a page
whose purpose is to show exactly what would be written.

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
| `--labels` | Re-read the labels from Wikidata and refresh `labels.json`. Without it, cached labels are used and the page contacts nothing. |
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
| `is_chublet` | Whether it already carries the whole identity block. |
| `checked` | Date of the lookup. |

Six keys are tried, in decreasing order of confidence. The first two are the
identity block read back: `P2888` holding the entry URL, and `P217` holding the
slug inside collection `Q141190255`. An item carrying either *is* this entry,
so they run before anything that has to be inferred. The other four look
outward: repository URL, DOI, CRAN package, PyPI package. Repository URLs are
queried in several spellings, because Wikidata holds whatever the editor pasted
-- with and without a trailing slash, with and without `.git`, occasionally
over http.

The slug lookup asks for `P217` *and* its `P195` qualifier in one pattern. An
inventory number read without its register is a string with no referent, and
matching on it alone would accept a museum object numbered `tabula`. It walks
statement nodes rather than truthy triples, which costs the query service more
per value, so it goes in batches of fifty rather than a hundred.

**Both identity keys are empty until the first push.** Nothing carries `P2888`
or `P217` in this collection before this import puts it there, so on a first
run they are two round trips that find nothing. They earn their place afterwards:
once items are written, they are the only keys that identify an entry rather
than infer it, and they are what makes a second run recognise its own work.

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
| `--set SECTION VALUE QID` | Resolve one value, e.g. `--set version_control_system Git Q186055`. Repeatable. |
| `--path FILE` | Create or update a different vocabulary file. |
| `--csv PATH`, `--all-categories` | As above. |

`--set` exists because editing the JSON by hand works right up until it does
not: one wrong bracket and every step fails with a parse error rather than with
the thing you actually got wrong. It checks that the section exists, that the
value is one the data contains, and that the Q-id looks like a Q-id, and says
which of the three failed.

Label search is a good way to find a candidate and a bad way to choose one, so
the choice stays with a person. `push` skips a statement whose value is
unresolved rather than guessing: an invented Q-id is a wrong statement that
looks like a right one.

### `categories`

```bash
python py/wikidata/main.py categories            # write out/category-reconciliation.csv
python py/wikidata/main.py categories --suggest  # with Wikidata candidates
python py/wikidata/main.py categories --verify   # is the Q-id you chose the right one?
python py/wikidata/main.py categories --apply    # read a filled one back
```

`unresolved-class` blocks every single item: the chublet class says an item
belongs to this effort and nothing says what kind of software it is. The
category column knows -- but *Packages and libraries* is open-archaeo's phrase,
not a Wikidata item, and choosing the item is a judgement. Seven values, eight
rows with the superclass, and one column to fill.

| Column | What it is |
|---|---|
| `section` | `item_class` or `superclass` -- which part of `vocabulary.json` `--apply` writes it into. |
| `value` | The category as it appears in open-archaeo. |
| `kind` | `software` for the three this import writes, `other` for the rest, `every item` for a superclass. |
| `uses_software` | How many of the 416 software entries carry it. |
| `uses_all` | How many of all 562 do. |
| `examples` | Three tools, for sanity. |
| `search_term` | What to search Wikidata for, where that differs from the phrase. Editable. |
| `qid` | **The column you fill.** |
| `qid_label` | Search hits from `--suggest`. Never decides. |
| `note` | What the decision actually is. open-archaeo defines its categories nowhere, so these notes are the closest thing to a scope note there is. |

**Not sliced, and not limited to the software subset.** *Guides* and *Lists and
datasets* describe entries this import does not touch yet, but they will be the
same items when it does, and deciding them together is what keeps one term from
acquiring two Q-ids. `--apply` writes only the three software categories into
`item_class`; the others are recorded and reported as deferred.

**What `--verify` cannot do is read.** It checks the *shape* of a choice --
that the item is a class, that other items use it, that it is not an article
with a matching title. Whether the class means what the category means is still
yours to judge, and a plausible `ok` is not agreement: `product` in the sense
of a chemical reaction is a perfectly well-formed class with real usage, and
entirely the wrong item for a register of software.

**`--verify` is how you say yes.** A search hit only tells you an item exists
whose label matches; the question is whether it is a *class that software items
are already instances of*. For every filled `qid` the step reports what the
item says it is, whether it is a class at all, and how many items use it as a
`P31` value -- then flags the three ways a choice goes wrong: an item that is a
scholarly article or a patent with a matching title, an item that is neither a
subclass of anything nor ever stated, and a class with fewer than five uses,
which is usually either the wrong one or a duplicate of the right one. A class
in real use beats a technically defensible one nobody states: the point of the
statement is to put these tools where people looking for tools will find them.

Fill `qid` with the bare Q-number -- `Q188860`, not the whole candidate line.
`qid_label` is a suggestion column and `--apply` never reads it.

**The superclass row is a modelling question, not a lookup.** The chublet class
is documented as a subclass of `Q73899440`. If that `P279` holds, stating the
superclass on every item as well is redundant for any query written
`wdt:P31/wdt:P279*`. Leaving the `qid` empty states only the chublet class;
filling it states both. That is why it is a row in a sheet rather than a
constant in `model.py`.

### `subjects`

```bash
python py/wikidata/main.py subjects            # write out/tag-reconciliation.csv
python py/wikidata/main.py subjects --suggest  # with Wikidata candidates
python py/wikidata/main.py subjects --apply    # read a filled one back
```

`P921` main subject is the largest block of unresolved values in the import --
56 terms across all 416 entries -- and the only one that cannot be derived from
a URL. It has to be decided term by term, so it gets a worksheet of its own
rather than a line in `vocab --suggest`.

**The scope notes make it tractable.** `tags.md` sits in the repository, is
used by nothing else, and carries a one-line definition for 55 of the 56 tags.
That definition is the difference between matching *Seriation* to the right
Wikidata item and matching it to a plausible wrong one, so the worksheet puts
it beside every term, together with the use count and three example tools.

| Column | What it is |
|---|---|
| `tag` | The term as it appears in open-archaeo. |
| `kind` | `subject`, `form` or `catch-all` -- see below. Editable. |
| `uses_software` | How many of the 416 software entries carry it. |
| `uses_all` | How many of all 562 entries do. |
| `scope_note` | From `tags.md`. |
| `examples` | Three tools carrying the tag, for sanity. |
| `search_term` | What to search Wikidata for; differs from the tag where the tag is a phrase. Editable. |
| `qid` | **The column you fill.** |
| `qid_label` | Search hits from `--suggest`, for choosing between. Never decides. |
| `note` | Anything worth recording, including two data problems found on the way. |

**Not every tag is a subject.** Six are marked otherwise, and the distinction
matters because `P921` asserts what a tool is *about*:

- `catch-all` -- *Bits and bobs* is open-archaeo's own word for miscellaneous
  and sits on 17 software entries. Importing it as a subject would assert that
  seventeen tools are about miscellany. *Lists* is the same case.
- `form` -- *Datasets*, *Templates*, *Platforms and publications*,
  *Educational resources and practical guides* say what a thing **is**, not
  what it is about. They belong on `P31`, or nowhere.

`--apply` refuses to write those into the `P921` vocabulary even if someone
fills in a Q-id, and says which and why. It also refuses anything that is not
shaped like a Q-id, and anything that is not a tag in the data.

**Two data problems the worksheet reports.** *Harris matrix* has no scope note
because `tags.md` spells it *Harrix matrix* -- a typo upstream. And the CSV
carries both spellings, ten entries under the correct one and one under the
typo. Both are worth an upstream issue rather than a local fix: open-archaeo is
the register, and correcting it here would put the fix in the wrong place.

**This step is deliberately not sliced.** The subject vocabulary is shared
between the two hackathon teams, so a worksheet covering half the data would
produce half a vocabulary and two different Q-ids for the same term. It is also
the natural handover format: whoever reconciles fills the `qid` column,
`--apply` reads it back, and both halves end up using the same items.

`P921` is the choice here over `P366` has use, which would read as *what the
tool is for* rather than *what it is about*. For something like *Radiocarbon
dating, calibration and sequencing* the two are nearly the same claim; for
*Zooarchaeology* they are not, and `P921` is the safer of the two.

### `push`

| Flag | Effect |
|---|---|
| `--live` | **Actually write.** Without it nothing leaves the machine. |
| `--create` | Create an item for every row with no Q-id, instead of adding statements to matched ones. |
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

Without `--create`, only rows that already have a `qid` are touched, and
statements that already exist are skipped, so re-running is safe.

#### `push --create`

Creates an item for every row that has no Q-id: label from `name`, a generated
description, and every statement at once in a single `wbeditentity` call.

**It works without a concordance**, and it has to: an entry with no Q-id
anywhere is exactly what this mode is for, so requiring `reconcile` first would
make the slow step a precondition of the step that does not need it. With no
concordance file the rows come from the table and every entry counts as not yet
in Wikidata; the file is written once the items exist. The
new Q-id is written back into the concordance immediately -- a created item
whose Q-id is not recorded is a duplicate waiting to be made on the next run.

It is a separate mode and not the default because it is the only thing in this
package that cannot be undone by editing. A wrong statement can be removed; a
duplicate item has to be *merged*, by a person, and merging is exactly the work
that different spellings of the same tool make hard.

Two rails, both deliberate:

- **It refuses while any other blocked issue stands.** `not-reconciled` is
  exempt -- that is the issue creation answers. Everything else means the item
  would be created in a state the preview already calls wrong, and a wrong new
  item has to be found again before it can be fixed. In practice this means
  `categories --apply` comes first.
- **It warns for every row that has never been reconciled.** Creating without
  looking is how duplicates are made. The warning does not stop the run: with
  the identity block in place, a duplicate is at least *findable* afterwards --
  `P217` in collection `Q141190255` is a key nothing else in Wikidata uses, so
  the merge candidates can be listed rather than hunted.

The description is generated rather than taken from open-archaeo: `R package
for archaeology`, `software for archaeology, for Blender`. The register's own
description is a sentence, sentence-cased, median 93 characters, and it
summarises -- a Wikidata description disambiguates instead, in a few lower-case
words with no full stop. A category with no template gets no description rather
than a guessed one, and the dry run says which those are.

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
| `--out-dir DIR` | Where to write (default `docs/`). |
| `--verify` | Run every query against WDQS before writing. |
| `--strict` | With `--verify`, fail the build on a failing query. |

`queries.py` is the source; the step writes `docs/sparql.html` and
`docs/queries/*.rq` from it, so the two cannot drift apart. Nine queries, of
which three are worklists rather than reports -- entries with a repository but
no licence, repository statements missing the required `P8423` qualifier, and
items whose identity block is incomplete. For those, an empty result is the
healthy one. One more answers the identifying question -- *which item is this
open-archaeo entry* -- from the slug.

Two deviations from the query pages in the `wdt-*` repositories, both
deliberate:

- **A live endpoint, not Pyodide.** Those pages parse a static Turtle file in
  the browser so an archived copy stays queryable with no service to keep
  alive. Here the graph *is* Wikidata, so there is nothing to ship. The cost is
  real: the page needs `query.wikidata.org` to be up, and a query typed into it
  leaves the machine.
- **`queries.py`, not `queries.yaml`.** A YAML file would mean a parser
  dependency for one list of strings, and this package installs nothing.

**Publishing.** Everything generated goes to `docs/` at the repository root,
which is the folder GitHub Pages serves when Pages is set to *deploy from a
branch*. As this repository stands, Pages is instead driven by
`.github/workflows/hugo.yml`, which uploads Hugo's `./public` -- so `docs/` is
not served until you either switch Pages to the `/docs` folder in the settings,
or build into Hugo's static directory instead with `--out-dir static`.

Locally, `python -m http.server` inside `docs/` serves both pages. Opening
`sparql.html` over `file://` does not work, because the browser blocks the
request to the query service; `preview.html` and `index.html` open fine either
way.

### `site`

```bash
python py/wikidata/main.py site
```

Writes `docs/index.html`, a landing page linking the two generated pages and
the two documents. It marks anything not generated yet, so an incomplete
`docs/` says so rather than offering dead links.

## Three modelling decisions

**The identity block.** Six statements go on every item whatever the row
contains: `P31` the chublet class, `P6104` the WikiProject, `P361` part of
open-archaeo and of chublets.software, `P195` open-archaeo as the collection,
`P217` the slug as inventory number qualified by that collection, and `P2888`
the entry URL. The first four say which set the item belongs to; the last two
say which entry it is, and that is a different question -- without them the
import cannot be checked row by row against its source, only counted.

They live in `IDENTITY_STATEMENTS` and `slug_claims()` in `model.py`, and every
other module reads them from there: the preflight resolves those Q-ids, the
preview labels them, `reconcile` builds its "already a chublet" query out of
them. Adding a seventh statement is one edit.

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

`all` does this in one command. Spelled out, so that each step is inspectable:

```bash
python py/wikidata/main.py --offline        # does the data still transform?
python py/wikidata/main.py preview          # every item and every problem, in a browser
python py/wikidata/main.py                  # do the identifiers still hold?
python py/wikidata/main.py reconcile        # what is in Wikidata already?
python py/wikidata/main.py vocab --suggest  # find candidates, choose by hand
python py/wikidata/main.py categories --suggest  # the seven classes, then --apply
python py/wikidata/main.py subjects         # the 56 subject terms, with their definitions
python py/wikidata/main.py preview --labels # look again: now with Q-ids resolved
python py/wikidata/main.py push             # the dry run, as text
python py/wikidata/main.py push --only <id> --only <id> --only <id> --live
python py/wikidata/main.py sparql           # publish the queries that check it
python py/wikidata/main.py site             # and the index that links them
```

Steps two and six are the ones worth slowing down on, and they are the same
step twice: once before the data is reconciled, to check the shape of the
statements, and once after, to check the values. The page ends with the command
for the first three ready items, which is the right size for a batch you intend
to open in a browser afterwards.

# The OpenRefine slice

208 of the 416 software entries in open-archaeo, to be modelled and uploaded to
Wikidata with OpenRefine. The other 208 are in `../Python/`, going in through
the Action API. Neither slice overlaps the other, so the two teams can work at
the same time without editing the same items.

Regenerate with `python py/main.py split`; the split is deterministic, so the
same file comes back. It is stratified rather than random: both slices carry
roughly half of every category, half the registry entries, half the DOIs, half
the archived snapshots. That is deliberate -- a random split would leave one
team with every CRAN package and neither team seeing the whole shape of the
problem.

The mapping itself is documented once, in `docs/MAPPING.md`. This
file is about doing it in OpenRefine.

## Before anything else

Two statements go on **every** item, whatever else is known about it:

| Property | Value |
|---|---|
| `P31` instance of | `Q141115627` |
| `P6104` maintained by WikiProject | `Q141169143` |

The class alone would also catch research software modelled by other
communities. `P6104` is what draws the boundary and makes the set retrievable
as a set, which is how both teams will check each other's progress.

## Setup

1. OpenRefine 3.7 or later, with the Wikibase extension (bundled since 3.5).
2. **Wikidata → Select Wikibase instance → Wikidata**, then log in with the
   account that will make the edits.
3. Create the project from `open-archaeo-software.csv`. Set the character
   encoding to UTF-8 and leave "parse cell text into numbers" **off**. `id` is
   a six-character hexadecimal string, and 38 of the 416 look like numbers to a
   parser -- `584689` becomes an integer and `692e63` becomes 6.92e+65, which
   is not a joinable identifier any more.

## Columns that hold more than one value

Six columns are pipe-separated: `tags`, `authors`, `repository`,
`repository_host`, `registry`, `registry_name`, `internetarchive`. For the ones
you intend to model, use **Edit cells → Split multi-valued cells** with the
separator `|`. Everything else in the row stays on the first line, which is
what the Wikidata schema editor expects.

`repository` and `repository_host` are parallel: the second value of one
belongs with the second value of the other. Split them together, not
separately, or the pairing is lost. Only one entry in the whole dataset has
more than one repository, so this is a corner worth knowing about rather than
a daily concern.

## Columns that hold more than they appear to

Four GREL expressions turn one column into a second statement. This is where
most of the value in this dataset is, and none of it is visible in the CSV.

**The version control system, from the forge.** `P8423` is a *required*
qualifier on `P1324` -- a repository statement without it is a constraint
violation, not merely an incomplete one. Add a column from `repository_host`:

```
if(or(value=="GitHub", value=="GitHub Gist", value=="GitLab", value=="Codeberg"),
   "Git",
   "")
```

Those four are every forge that occurs in the dataset except Bitbucket, which
hosts both Git and Mercurial and so stays empty. Leave that row without the
qualifier rather than guessing; there is exactly one of them.

**The archive date, from the archive URL.** The Internet Archive path embeds
its own timestamp, so `P2960` comes free alongside `P1065`. Add a column from
`internetarchive`:

```
value.match(/.*_-_(\d{4}-\d{2}-\d{2})_.*/)[0]
```

221 of the 222 snapshots parse. Set the date precision to **day** in the
schema: the time in the path is when the crawl ran, which is not a claim worth
making to the second.

**The CRAN package name, from the CRAN URL.** As an external identifier
(`P5565`) this is round-trippable and constraint-checked, where a bare link is
neither. Add a column from `registry`:

```
if(cells["registry_name"].value == "CRAN",
   value.match(/.*package=([^\/&?]+).*/)[0],
   null)
```

**The PyPI package name** (`P5568`), same idea, one entry in the dataset:

```
if(cells["registry_name"].value == "PyPI",
   value.match(/.*pypi\.org\/project\/([^\/?#]+).*/)[0],
   null)
```

## Reconciling

Reconcile the `name` column against Wikidata, type **software (Q7397)**.

**Do not accept matches on the name alone.** `name` is not unique in
open-archaeo -- that is why the dataset has a `slug` column at all -- and
several of these tools share a name with something entirely unrelated. In the
reconciliation dialogue, add `repository` as a property to match against
`P1324`. A match with an agreeing repository is safe; a match without one needs
a person to look at it.

Work through the results with the `repository` column visible, and reject
anything whose repository disagrees. It is much cheaper to reject a wrong match
now than to find it after the upload.

For entries that reconcile to nothing, decide deliberately whether to create a
new item. Not every script in this list needs one, and the schema editor will
happily create 208 of them if you let it.

## The vocabulary: your job for both teams

`P277` programmed in, `P1547` depends on software and `P921` main subject all
take *items* as values, and the CSV gives strings -- `R`, `QGIS`, `Radiocarbon
dating`. Reconciling those columns is exactly what OpenRefine is good at and
what the Python route has to do by hand, so **this slice owns the vocabulary
for both halves**.

- `platform` where `platform_role` is `language` → reconcile against
  programming language (Q9143), feeds `P277`.
- `platform` where `platform_role` is `host application` → reconcile against
  software (Q7397), feeds `P1547`.
- `tags` → reconcile against Wikidata generally; 56 distinct terms, and several
  will need judgement rather than a top hit.

When you have settled them, export the chosen Q-ids as a two-column CSV
(`value,qid`) and hand it over. The Python side keeps them in
`py/wikidata/vocabulary.json`, and until they arrive it refuses to write those
statements at all rather than guess. One vocabulary, two importers.

## Building the schema

**Wikidata → Edit Wikidata schema.** Statements to model, beyond the two
obligatory ones:

| Statement | From | Notes |
|---|---|---|
| `P1324` source code repository URL | `repository` | with `P8423` as a qualifier from the derived column, and `P1065` + `P2960` where a snapshot exists |
| `P856` official website | `website` | |
| `P5565` CRAN project | derived column | external identifier, not a URL |
| `P5568` PyPI project | derived column | |
| `P356` DOI | `doi` | **see the caveat below** |
| `P277` programmed in | reconciled `platform` | |
| `P1547` depends on software | reconciled `platform` | |
| `P921` main subject | reconciled `tags` | |
| `P2561` name | `name`, as monolingual text `en` | next to the label, not instead of it |
| `P973` described at URL | `url` | interim: no open-archaeo property exists yet |

Two things not to model:

**Zenodo DOIs.** 24 of the 34 DOIs begin `10.5281`, which is Zenodo. A Zenodo
DOI is a *deposit* DOI: it identifies a release, not the tool, so it belongs as
a qualifier on `P348` and is simply wrong at item level. Facet `doi` on
`starts with 10.5281` and exclude those rows from the `P356` statement.

**Mismatched archive snapshots.** Fourteen entries across the full dataset list
a repository on one forge and a snapshot of another -- the tool moved, the crawl
did not follow. Attaching them would claim the Internet Archive holds a copy it
never saw. Compare the host in `repository` with the beginning of the
`internetarchive` path and drop the qualifier where they disagree.

## Uploading

Preview first: the schema editor's **Issues** tab catches missing required
qualifiers and malformed values before anything is sent.

Then either **Wikidata → Upload edits to Wikidata**, or export QuickStatements
and run them yourself. Upload directly if you want OpenRefine's edit grouping
and its rate limiting; export to QuickStatements if you want to read the
statements as text one last time. For a hackathon, exporting first and reading
the first twenty lines is time well spent.

Give the edit group a summary that names the source, for example
`open-archaeo import (OpenRefine slice)`. Two teams editing the same
WikiProject at the same time will want to tell their edits apart afterwards.

## Checking your work

Open `docs/sparql.html` in a browser -- it queries Wikidata live
and is shared with the other team. Three of its queries are worklists rather
than reports:

- entries with a repository but no licence (open-archaeo records none at all,
  so this one will be long),
- repository statements missing the required `P8423` qualifier -- anything here
  is a bug in the import, since the value is derivable,
- items carrying only one of the two obligatory statements, which usually means
  an interrupted upload.

For those three, an empty result is the healthy one.

## Handing back

Export `id` and the reconciled Q-id as a two-column CSV. That is the merge
contract between the two halves: it lets the concordance in
`out/open-archaeo-concordance.csv` be completed for the whole 416 without
either team re-querying what the other already established.

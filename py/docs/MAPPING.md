# Mapping open-archaeo to Wikidata

How an entry in `out/open-archaeo-software.csv` becomes a set of Wikidata
statements. `py/README.md` documents the *processing*; this file documents the
*target model*, and `py/crosswalk_codemeta_wikidata_chublets.csv` places both
next to CodeMeta and the planned chublets properties.

Counts below are for the 416-entry software subset.

Property numbers marked **verified** were checked against Wikidata while
writing this file. Everything else is a modelling decision and open to
discussion.

## Two statements on every item

Independent of what open-archaeo records, every chublet carries the same two
statements. They are what makes the set queryable as a set.

| Property | Value | Why |
|---|---|---|
| `P31` instance of | `Q141115627` | Puts the item in the class, which is a subclass of `Q73899440` belonging to `Q141115774`. |
| `P6104` maintained by WikiProject | `Q141169143` | **verified.** Ties the item to the WikiProject, so `haswbstatement:P6104=Q141169143` retrieves the whole set without a curated focus list. |

`P6104` is the more important of the two in practice. Without it there is no
way to ask *which items belong to this effort* -- class membership alone will
also catch research software modelled by anyone else.

## Column by column

| Source column | Filled | Property | Qualifiers | Status |
|---|---|---|---|---|
| `repository` (six forge columns) | 390 | `P1324` source code repository URL | `P8423` **required**, plus `P1065` + `P2960` from `internetarchive` | verified |
| `website` | 121 | `P856` official website | -- | verified |
| `doi` | 34 | `P356` DOI | on `P348` when it is a release DOI | verified |
| `cran` | 39 | `P5565` CRAN project | -- | verified |
| `pypi` | 1 | `P5568` PyPI project | -- | verified |
| `internetarchive` | 222 | `P1065` archive URL | `P2960` archive date | verified, as qualifier |
| `publication` | 25 | `P1343` described by source | item, not URL -- see below | decision |
| `category` | 416 | `P31` instance of | -- | decision, see below |
| `platform` (`language`) | 301 | `P277` programmed in | -- | verified property, derived value |
| `platform` (`host application`) | 34 | `P1547` depends on software | -- | verified property, derived value |
| `platform` (`deployment`) | 8 | refines `P31` | -- | decision |
| `tags` | 416 | `P921` main subject | -- | needs 59 reconciliations |
| `authors` | 416 | `P178` developer | `P1545` series ordinal | see below |
| `name` | 416 | label **and** `P2561` name | -- | verified |
| `description` | 416 | item description | -- | needs rewriting |
| `blogpost`, `youtube` | 4 | `P973` described at URL | -- | decision |
| `url` (open-archaeo page) | 416 | `P973` described at URL | -- | interim, see below |
| `twitter`, `notes` | 0 / 2 | -- | -- | not import material |

## What the columns contain beyond their face value

The transformation is lossless, but several columns carry *more than one*
statement inside a single string. Six cases, all deterministic:

**1. The forge URL names its version control system.** `P1324` carries a
*required qualifier* constraint for `P8423` version control system -- an item
without it is a constraint violation, not merely an incomplete one. The host
supplies the value: Git for GitHub, Gist, GitLab and Codeberg (385 entries),
and Bitbucket ambiguous between Git and Mercurial (1 entry). `repository_host`
therefore is not decoration; it is what satisfies the constraint. `P10627` web
interface software is available on the same statement if the forge itself
should be named.

**2. The forge URL names its owner.** 239 distinct owners across 463 GitHub
URLs, and the owner equals `author1_name` in 427 of them. Regex-extracting the
owner is more reliable than parsing the author string, because it yields a
`P2037` GitHub username that reconciles a *person or organisation item*,
whereas a bare name string reconciles nothing. Note the direction: `P2037`
belongs on the developer item, not on the software item.

**3. The Internet Archive URL contains its own timestamp.** The snapshot path
is `github.com-<owner>-<repo>_-_YYYY-MM-DD_HH-MM-SS`, and 221 of the 222
snapshots in the subset parse, spanning 2014-07-18 to 2021-07-06. That is a
free `P2960` archive date beside the `P1065` archive URL, and both are on the
allowed-qualifier list for `P1324`. The date also proves the repository existed
at that moment, which bounds `P571` inception from above -- worth recording as
a note, not as a statement.

**4. The registry URL contains the package name.** `https://CRAN.R-project.org/package=tabula`
yields `tabula`, `https://pypi.org/project/iosacal/` yields `iosacal`. As
external identifiers (`P5565`, `P5568`) these are far more useful than the
`P973` described at URL that the current README suggests: they are round-trippable,
constraint-checked, and they let Wikidata tools resolve the package rather than
merely link to a page.

**5. The DOI prefix names the registrant.** 24 of the 34 DOIs in the subset are
`10.5281`, that is Zenodo. A Zenodo DOI is a *deposit* DOI and usually refers
to a specific release, which in Wikidata means `P356` as a qualifier on `P348`
rather than a statement on the item. The remaining ten are publisher DOIs and
belong at item level or on the publication. Splitting on the prefix separates
the two cases without a lookup.

**6. `publication` is an article, not a link.** 20 of the 25 values are
`doi.org` URLs. Modelled as `P973` described at URL the article disappears;
modelled as `P1343` described by source it becomes an item, and the DOI is the
key that finds or creates it. This is the single largest gain in expressiveness
available from the existing data.

Two smaller ones: author order is meaningful and survives as `P1545` series
ordinal on `P178`, and the one YouTube URL carries a video ID for `P1651` --
not worth automating for a single row.

## Decisions that still have to be made

**The class behind `category`.** Packages and libraries suggest software
library (`Q188860`), standalone software suggests application software
(`Q166142`), and for scripts there is no established narrower class than
software (`Q7397`). Since every item also carries the chublets class
(`Q141115627`), the question is whether the finer class is worth a second
`P31` value or whether the category is better expressed as `P279` on the class
items themselves.

**An open-archaeo identifier.** There is no property for open-archaeo, so the
entry page currently has to go in as `P973` described at URL. The precedent for
doing this properly is `P6830` swMATH work ID: a domain registry with an
external-identifier property of its own. Proposing `open-archaeo ID` with the
slug as its value would make the registry a first-class source in Wikidata and
give chublets a stable join key in both directions. The minted `id` column is
**not** a candidate -- it is a function of the slug, so it changes when an entry
is renamed.

**Descriptions.** Wikidata descriptions are short, lower case and carry no
terminal punctuation. These are sentences: 348 end in a full stop, 413 begin
with a capital. Usable, but only after rewriting, and rewriting 416 of them is
the largest piece of manual work in the whole import.

## What open-archaeo does not record

- **Copyright licence (`P275`).** `P1324` carries a constraint that items
  should state a licence, and open-archaeo records none for any entry. This is
  the largest gap and it has to come from the repositories.
- **`P571` inception** and **`P348` software version**.
- **Programming language for the 73 entries with an empty `platform`.**
- **Software Heritage.** Upstream lists this as a planned addition; the target
  property already exists and is `P6138` SWHID.

## Reconcile before creating anything

Many of these tools are in Wikidata already. `repository` is the strongest join
key, `doi` the second:

```sparql
SELECT ?item ?itemLabel ?repo WHERE {
  VALUES ?repo { <https://github.com/ISAAKiel/quantAAR> }
  ?item wdt:P1324 ?repo .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

Once `P6104` is set, the reverse question -- what is already covered -- is a
single search: `haswbstatement:P6104=Q141169143`.

## Shape of a generated statement block

Illustrative, for one entry, in QuickStatements v1 syntax:

```
Q<item>	P31	Q141115627
Q<item>	P6104	Q141169143
Q<item>	P2561	en:"quantAAR"
Q<item>	P1324	"https://github.com/ISAAKiel/quantAAR"	P8423	Q<Git>	P1065	"https://archive.org/details/github.com-ISAAKiel-quantAAR_-_2020-07-09_13-14-14"	P2960	+2020-07-09T00:00:00Z/11
Q<item>	P277	Q<R>
Q<item>	P921	Q<tag item>
```

The `P8423` and `P2960` values come from the two derivations above, not from
any column that exists in the source.

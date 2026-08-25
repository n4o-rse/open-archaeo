# What open-archaeo does not hold

Short answer: the 31 columns are close to mined out, and that is not a failure
of the dataset. open-archaeo is a *register* -- it says which tools exist, who
made them and where the code is. It was never a metadata record, and the things
missing from the import are the things a register does not carry.

The columns are worth reading as a set of **resolvable identifiers**. Each URL
in them points at a document that does hold the metadata. That is where the
next round of enrichment comes from, not from squeezing the CSV harder.

Everything below about the CSV itself was measured against the 416-entry
software subset. Everything about the external sources was **not** measured --
the sandbox this was written in cannot reach them -- so those rows are claims
about what the APIs return, to be checked before relying on them.

## What is already squeezed out

Six columns yield more than one statement each, and none of it is visible in
the CSV:

| Column | Also yields | Coverage |
|---|---|---|
| forge URL | the version control system for the required `P8423` qualifier | 385 of 390 |
| forge URL | the account name, so the owner reconciles through `P2037` rather than a name string | 463 URLs, 239 distinct owners |
| `internetarchive` | the snapshot date, embedded in the path, for `P2960` | 221 of 222 |
| `cran` | the package name, so `P5565` instead of a bare link | 39 of 39 |
| `pypi` | the package name, for `P5568` | 1 of 1 |
| `DOI` | the registrant: `10.5281` is Zenodo, a release DOI, which belongs on `P348` and not on the item | 24 of 34 |

## One seam still open in the data

**Authors.** 502 mentions across the software subset, 283 distinct. 221 of
those look like account names rather than personal names -- and 187 are
demonstrably the owner of a forge URL somewhere in the same dataset. That means
they can be reconciled through `P2037` GitHub username, which resolves to a
*person or organisation item*, rather than by matching a display string, which
resolves to nothing.

`P178` developer is therefore tractable and currently not emitted at all. It is
reported as an `unresolved-author` issue on the preview page so the size of the
gap stays visible. The remaining 96 names, the ones with spaces in them, are
ordinary human reconciliation.

## One thing that looked promising and is not

The 73 entries with an empty `platform` column: could the language be read out
of the description text? Tested against a dozen patterns -- R, Python, QGIS,
JavaScript, Java, MATLAB, Blender, ArcGIS, Excel, PHP, C++, Ruby -- across
every field of those rows.

**One hit.** Not 30, not 10. One. The descriptions say what a tool does, not
what it is written in, and inferring from them would be guesswork dressed as
extraction. That gap has to come from the repository.

## What is missing, and where it actually lives

| Gap | Source | What it should give |
|---|---|---|
| **`P275` copyright licence** -- the largest, missing for all 416 | GitHub API `/repos/{owner}/{repo}`, field `license.spdx_id` | An SPDX identifier per repository. `P1324` carries a constraint expecting the item to state a licence, so this is the gap that turns into a constraint violation. |
| `P571` inception | same call, `created_at` | Repository creation, which is a defensible proxy and not the same as the tool's inception. Worth a qualifier saying so. |
| `P277` for the 73 without a platform | same call, `language` | GitHub's own detection, which is imperfect but better than the description. |
| `P921` further subjects | same call, `topics` | Repository topics, alongside the open-archaeo tags. |
| **abandonware** (`P31` with `P580`/`P582`) | same call, `archived` | A tool whose repository is archived is a tool that stopped. open-archaeo has no way to say this. |
| `P348` version, `P577` per release | GitHub `/releases`, or CRAN `DESCRIPTION`, or the Zenodo record | Version strings with their dates, which is the pattern the WikiProject documents. |
| `P275`, `P178` with ORCID, `P577` | CRAN `DESCRIPTION` for the 39 CRAN packages | CRAN requires a licence field, so those 39 are the cheapest licences in the set. |
| `P356` at release level, `P275`, authors with ORCID | Zenodo API for the 24 Zenodo DOIs | Deposit metadata, which is richer than anything in the CSV. |
| `P1343` reference publication as an *item* | Crossref or DataCite, from the 25 `publication` DOIs | Enough to create or find the article item, rather than linking a URL. |
| **`P6138` SWHID** | Software Heritage API, by repository URL | The archival identifier. open-archaeo lists this as a planned column; the property already exists. |
| CodeMeta and CFF fields wholesale | `codemeta.json` or `CITATION.cff` in the repository | Where a project has one, it is a metadata record written by the authors, which beats anything inferred. |

## The order worth doing them in

1. **GitHub API for every repository.** One call per entry, 390 calls, and it
   closes the licence gap, the inception gap and part of the language gap at
   once. Rate-limited to 60 an hour unauthenticated and 5,000 with a token, so
   it is an afternoon either way.
2. **CRAN `DESCRIPTION` for the 39 packages.** Small, and CRAN mandates a
   licence field, so the hit rate is 100%.
3. **Zenodo for the 24 deposits.** Gives release-level metadata, which is what
   `P348` needs to be modelled properly.
4. **`CITATION.cff` and `codemeta.json`.** Fewest hits, best quality: where one
   exists, it was written by the person who wrote the tool.
5. **Software Heritage.** Once the repository URLs are settled.

Each of those would become a cache file beside the CSV rather than an edit to
it -- open-archaeo is upstream and should stay the register it is. The
concordance already sets the pattern: a file that says what is known about each
entry, rebuilt rather than hand-maintained.

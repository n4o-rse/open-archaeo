# `open-archaeo-software.csv`

Generated file -- do not edit by hand. Rebuild with:

```bash
python py/main.py transform
```

## Provenance

- Source: `open-archaeo.csv` in the repository root
- Scope: Packages and libraries, Standalone software, Scripts
- Rows: 416
- Columns: 22

The transformation is lossless with respect to the source: every non-empty value reappears, only reshaped. Six forge columns collapse into `repository` plus a parallel `repository_host`, two registry columns into `registry` plus `registry_name`, and the five tag and six author columns into one field each.

Multi-valued fields use `|` as separator. Where two columns are described as parallel, their values line up position by position.

## Columns

`Filled` counts rows with a non-empty value. `Property` is the suggested Wikidata mapping; entries marked `?` are modelling decisions rather than settled facts, and P1324, P856 and P356 are the only ones verified against Wikidata.

| Column | Source | Filled | Property | Content |
|---|---|---|---|---|
| `id` | derived | 416 | — | Six hexadecimal characters, `sha256(slug)` truncated. Unique across all 562 source entries. |
| `slug` | derived | 416 | — | Path segment under which the entry is published on open-archaeo.info. |
| `url` | derived | 416 | P973? | Resolvable page, base URL plus slug, percent-encoded. |
| `name` | `item_name` | 416 | label | Name of the tool as recorded upstream. Not unique. |
| `description` | `description` | 416 | — | One or two sentences describing the tool. Sentence case with terminal punctuation, so it needs rewriting before it can serve as a Wikidata description. |
| `category` | `category` | 416 | P31? | One of the three software categories. Determines the class, which is a choice: software library (Q188860), application software (Q166142), software (Q7397). |
| `platform` | `platform` | 343 | — | Language, host application or delivery form. See `platform_role`. |
| `platform_role` | derived | 343 | — | Which of the three `platform` means: `language`, `host application`, `deployment`, or empty. Routes the value to P277, P1547 or a P31 refinement respectively. |
| `tags` | `tag1`–`tag5` | 416 | P921? | Thematic subjects from a 59-value vocabulary, pipe-separated, zero to five per entry. Each term needs reconciling to an item. |
| `authors` | `author1_name`–`author6_name` | 416 | P2037? | Pipe-separated, in upstream order. Mostly forge usernames rather than personal names, so P2037 is a more reliable route than matching a name string to P178. |
| `repository` | `github`, `gist`, `gitlab`, `bitbucket`, `launchpad`, `codeberg` | 390 | P1324 | Pipe-separated repository URLs. |
| `repository_host` | derived | 390 | — | Parallel to `repository`, so each URL keeps its host. Can drive the P8423 version control system qualifier: Git for GitHub, GitLab and Codeberg; Bazaar for Launchpad; Bitbucket is ambiguous. |
| `registry` | `cran`, `pypi` | 40 | P973? | Package registry page. |
| `registry_name` | derived | 40 | — | Parallel to `registry`: `CRAN` or `PyPI`. |
| `doi` | `DOI` | 34 | P356 | Normalised to the bare `10.x/…` form, any `https://doi.org/` prefix removed. |
| `publication` | `publication` | 25 | P973? | URL of an accompanying paper, often itself a `doi.org` link. P1343 with an item would be richer than a bare URL. |
| `website` | `website` | 121 | P856 | Project homepage or documentation site. |
| `blogpost` | `blogpost` | 3 | P973? | A blog post about the tool. |
| `youtube` | `youtube` | 1 | P973? | A video about the tool. |
| `twitter` | `twitter` | 0 | — | Carried for losslessness. P2002 expects a username, not a URL, so this is not import material as it stands. |
| `internetarchive` | `internetarchive` | 222 | P1065? | Internet Archive snapshot of the repository. Normally a qualifier on P1324 rather than a statement of its own. |
| `notes` | `notes` | 2 | — | Editorial notes by the open-archaeo maintainers **about the dataset**, not about the tool. Not import material. |

## Controlled vocabularies

| Field | Cardinality | Distinct values in this file |
|---|---|---|
| `category` | exactly one | 3 |
| `platform` | zero or one | 22 |
| `platform_role` | zero or one | 3 |
| `tags` | zero to five | 56 |

## Known gaps

Wikidata expects several things open-archaeo does not record. These have to come from the repositories, the registries or Software Heritage:

- **Copyright licence (P275).** P1324 carries a constraint that items should state a licence. This is the largest single gap.
- **Inception (P571)** and **software version (P348)**.
- **Programming language** for the 73 rows with an empty `platform`.
- **Software Heritage identifier.** Listed upstream in `ToDo.md` as a planned addition.

Existing Wikidata items should be reconciled before anything is created; `repository` is the strongest join key, `doi` the second.

See `py/README.md` for the full audit and the slug derivation.

<!-- about.md is automatically preprended to README.md in R/csv2readme.R -->
# Open Archaeology Software & Resources

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.8299651.svg)](https://doi.org/10.5281/zenodo.8299651)
[![Paper](https://img.shields.io/badge/Paper-JOAD-green)](https://doi.org/10.5334/joad.111)

A list of open source archaeological software and resources

See [ToDo.md](https://github.com/zackbatist/open-archaeo/blob/master/ToDo.md) for a list of tools or resources that are in demand, but which currently do not exist or need to be significantly improved. See [tags.md](https://github.com/zackbatist/open-archaeo/blob/master/tags.md) for a description of all tags.

This readme and the [web interface](https://open-archaeo.info) are automatically generated from data stored in [open-archaeo.csv](https://github.com/zackbatist/open-archaeo/blob/master/open-archaeo.csv). Please update the csv when submitting a pull request.

---

## This fork: open-archaeo in Wikidata

This fork adds a Python pipeline (standard library only, no dependencies) that
reshapes the register into a machine-readable table and imports it into Wikidata
as a set of *chublets*. Nothing in the upstream data or the R site build is
changed; everything new lives under `py/`.

Full documentation: [`py/README.md`](py/README.md) for the data pipeline,
[`py/wikidata/README.md`](py/wikidata/README.md) for the import, and
[`py/docs/MAPPING.md`](py/docs/MAPPING.md) for the target data model.

### The whole chain, in one command

```bash
python py/wikidata/main.py all
```

That runs the read-only route in order and opens the preview in a browser:

| Step | What it does |
|---|---|
| `transform` | `open-archaeo.csv` -> `out/open-archaeo-software.csv` and its README |
| `vocab` | collects the controlled values that need a Q-id |
| `categories` | the `P31` class worksheet, `out/category-reconciliation.csv` |
| `subjects` | the `P921` subject worksheet, `out/tag-reconciliation.csv` |
| `check` | verifies data, endpoints, identifiers, vocabulary and plan |
| `preview` | `docs/preview.html`: every item as Wikidata would show it |
| `sparql` | `docs/sparql.html` and `docs/queries/*.rq` |
| `site` | `docs/index.html`, the landing page |

`--offline` skips everything that needs a connection, `--no-open` builds without
opening a browser, `--full` uses all 416 software entries instead of the working
slice. `reconcile` is not part of `all` -- it is slow and its result changes
rarely; `--reconcile` puts it back in.

### The decisions the chain cannot make

Two things need a person once, and the preview reports both as blocked until
they are made:

```bash
python py/wikidata/main.py categories --suggest   # candidates for the 7 categories
# fill the qid column in out/category-reconciliation.csv
python py/wikidata/main.py categories --verify    # is that Q-id really a class?
python py/wikidata/main.py categories --apply

python py/wikidata/main.py vocab --suggest        # candidates for 73 values
python py/wikidata/main.py vocab --set version_control_system Git Q186055
```

`P1324` source code repository URL requires a `P8423` version control system
qualifier, so the second one alone clears 390 entries.

### Writing to Wikidata

```bash
python py/wikidata/main.py push --create                 # dry run
python py/wikidata/main.py push --create --limit 1 --live  # one item, to look at
python py/wikidata/main.py push --create --skip-blocked --live
```

`push` is the only step that writes, `--live` is the only way past a dry run,
and neither is part of `all`. Credentials go in `py/wikidata/config.ini` (copy
`config.example.ini`); a bot password and a User-Agent naming a contact address
are both required before it will start.

---

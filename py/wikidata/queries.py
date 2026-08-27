#!/usr/bin/env python3
"""The example queries behind ``docs/sparql.html``.

One source, two products -- the HTML page and ``docs/queries/*.rq`` -- so they
cannot drift apart. This is the ``queries.yaml`` of the wdt-* repositories,
written as a Python module instead: this package installs nothing, and a YAML
file would drag in a parser for a single list of strings.

Prefixes live here once and are prepended at build time, not repeated in every
query.
"""

from __future__ import annotations

PAGE = {
    "title": "Chublets in Wikidata",
    "intro": (
        "Every chublet carries the same block of statements: it is an instance "
        "of <a href='https://www.wikidata.org/wiki/Q141115627'>Q141115627</a>, "
        "maintained by "
        "<a href='https://www.wikidata.org/wiki/Q141169143'>Q141169143</a>, "
        "part of <a href='https://www.wikidata.org/wiki/Q141190255'>open-archaeo"
        "</a> and of <a href='https://www.wikidata.org/wiki/Q141115774'>"
        "chublets.software</a>. Those make the set retrievable as a set; "
        "<code>P217</code> inventory number, holding the open-archaeo slug in "
        "collection <code>P195</code>, says which entry an item is. Edit any "
        "query and run it again -- it goes straight to the Wikidata Query "
        "Service from your browser."
    ),
    "footer": (
        "Queries run against <code>query.wikidata.org</code>. The mapping behind "
        "them is documented in <code>py/docs/MAPPING.md</code>; the concordance "
        "of what is already matched is <code>out/open-archaeo-concordance.csv</code>."
    ),
}

PREFIXES = """\
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>
"""

QUERIES = [
    {
        "id": "all-chublets",
        "title": "Everything currently tagged",
        "intro": "The whole set, with repository, licence and language where "
                 "they exist. This is the query the rest of the page varies.",
        "sparql": """\
SELECT ?item ?itemLabel ?itemDescription ?repo ?licenceLabel ?languageLabel
WHERE {
  ?item wdt:P31 wd:Q141115627 ;
        wdt:P6104 wd:Q141169143 .
  OPTIONAL { ?item wdt:P1324 ?repo . }
  OPTIONAL { ?item wdt:P275 ?licence . }
  OPTIONAL { ?item wdt:P277 ?language . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de". }
}
ORDER BY ?itemLabel""",
    },
    {
        "id": "count-by-language",
        "title": "How many per programming language",
        "intro": "P277 comes from open-archaeo's <code>platform</code> column "
                 "wherever that column names a language rather than a host "
                 "application. Entries with no language fall out of this count.",
        "sparql": """\
SELECT ?languageLabel (COUNT(DISTINCT ?item) AS ?tools)
WHERE {
  ?item wdt:P31 wd:Q141115627 ;
        wdt:P6104 wd:Q141169143 ;
        wdt:P277 ?language .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de". }
}
GROUP BY ?languageLabel
ORDER BY DESC(?tools)""",
    },
    {
        "id": "missing-licence",
        "title": "Has a repository but states no licence",
        "intro": "P1324 carries a constraint that the item should state a "
                 "licence, and open-archaeo records none for any entry. This is "
                 "the largest gap in the import and the most useful worklist on "
                 "the page: every row is a licence that has to be read off the "
                 "repository.",
        "sparql": """\
SELECT ?item ?itemLabel ?repo
WHERE {
  ?item wdt:P31 wd:Q141115627 ;
        wdt:P6104 wd:Q141169143 ;
        wdt:P1324 ?repo .
  FILTER NOT EXISTS { ?item wdt:P275 ?licence . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de". }
}
ORDER BY ?itemLabel""",
    },
    {
        "id": "missing-vcs-qualifier",
        "title": "Repository without the required version control qualifier",
        "intro": "P8423 is a <em>required</em> qualifier on P1324, so a "
                 "repository statement without it is a constraint violation "
                 "rather than merely an incomplete one. The value is derivable "
                 "from the forge, so anything listed here is a bug in the "
                 "import, not missing knowledge.",
        "sparql": """\
SELECT ?item ?itemLabel ?repo
WHERE {
  ?item wdt:P31 wd:Q141115627 ;
        wdt:P6104 wd:Q141169143 ;
        p:P1324 ?statement .
  ?statement ps:P1324 ?repo .
  FILTER NOT EXISTS { ?statement pq:P8423 ?vcs . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de". }
}
ORDER BY ?itemLabel""",
    },
    {
        "id": "archive-snapshots",
        "title": "Repositories with an archived snapshot",
        "intro": "The Internet Archive URL and its date both come out of the "
                 "single <code>internetarchive</code> column, because the "
                 "snapshot path embeds its own timestamp.",
        "sparql": """\
SELECT ?item ?itemLabel ?repo ?archive ?archiveDate
WHERE {
  ?item wdt:P31 wd:Q141115627 ;
        wdt:P6104 wd:Q141169143 ;
        p:P1324 ?statement .
  ?statement ps:P1324 ?repo ;
             pq:P1065 ?archive .
  OPTIONAL { ?statement pq:P2960 ?archiveDate . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de". }
}
ORDER BY DESC(?archiveDate)""",
    },
    {
        "id": "by-subject",
        "title": "Subjects, most used first",
        "intro": "P921 from open-archaeo's tag columns. Each of the 59 tags "
                 "needs its own Wikidata item, so this count also shows how far "
                 "that reconciliation has got.",
        "sparql": """\
SELECT ?subjectLabel (COUNT(DISTINCT ?item) AS ?tools)
WHERE {
  ?item wdt:P31 wd:Q141115627 ;
        wdt:P6104 wd:Q141169143 ;
        wdt:P921 ?subject .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de". }
}
GROUP BY ?subjectLabel
ORDER BY DESC(?tools)""",
    },
    {
        "id": "by-slug",
        "title": "Find an entry by its open-archaeo slug",
        "intro": "The identifying question, and the one the reconcile step "
                 "asks first: which item is <em>this</em> open-archaeo entry? "
                 "The slug sits in P217 inventory number, qualified by P195 "
                 "collection -- the qualifier is what stops the query from "
                 "matching an object numbered the same way in some other "
                 "register. Replace the slugs in the VALUES block with yours.",
        "sparql": """\
SELECT ?slug ?item ?itemLabel ?entry
WHERE {
  VALUES ?slug { "quantaar" "tabula" "rrtools" }
  ?item p:P217 ?statement .
  ?statement ps:P217 ?slug ;
             pq:P195 wd:Q141190255 .
  OPTIONAL { ?item wdt:P2888 ?entry . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de". }
}
ORDER BY ?slug""",
    },
    {
        "id": "half-tagged",
        "title": "An incomplete identity block",
        "intro": "A consistency check on the block itself. Items appear here "
                 "when they carry the chublet class but are missing one of the "
                 "statements that should always accompany it, which usually "
                 "means an interrupted import rather than a modelling "
                 "decision. An empty result is the healthy one.",
        "sparql": """\
SELECT ?item ?itemLabel ?missing
WHERE {
  ?item wdt:P31 wd:Q141115627 .
  {
    FILTER NOT EXISTS { ?item wdt:P6104 wd:Q141169143 . }
    BIND("P6104 WikiProject" AS ?missing)
  } UNION {
    FILTER NOT EXISTS { ?item wdt:P361 wd:Q141190255 . }
    BIND("P361 open-archaeo" AS ?missing)
  } UNION {
    FILTER NOT EXISTS { ?item wdt:P361 wd:Q141115774 . }
    BIND("P361 chublets.software" AS ?missing)
  } UNION {
    FILTER NOT EXISTS { ?item wdt:P195 wd:Q141190255 . }
    BIND("P195 collection" AS ?missing)
  } UNION {
    FILTER NOT EXISTS {
      ?item p:P217 [ pq:P195 wd:Q141190255 ] .
    }
    BIND("P217 slug" AS ?missing)
  } UNION {
    FILTER NOT EXISTS { ?item wdt:P2888 ?url . }
    BIND("P2888 entry URL" AS ?missing)
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de". }
}
ORDER BY ?missing ?itemLabel""",
    },
    {
        "id": "reconcile-by-repository",
        "title": "Reconcile a repository URL",
        "intro": "The lookup the <code>reconcile</code> step runs in batches. "
                 "Paste your own URLs into the VALUES block. Note that it does "
                 "<em>not</em> filter on the identity block -- the "
                 "point is to find items that exist but are not tagged yet.",
        "sparql": """\
SELECT ?repo ?item ?itemLabel ?tagged
WHERE {
  VALUES ?repo {
    <https://github.com/ISAAKiel/quantAAR>
    <https://github.com/tesselle/tabula>
    <https://github.com/benmarwick/rrtools>
  }
  ?item wdt:P1324 ?repo .
  BIND(EXISTS { ?item wdt:P6104 wd:Q141169143 } AS ?tagged)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de". }
}""",
    },
]

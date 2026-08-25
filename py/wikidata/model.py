#!/usr/bin/env python3
"""The model: which identifiers are used, and how a row becomes statements.

This is the single source of truth for the import, in the sense the
wikibase-federation use cases give the term: change the mapping here, nowhere
else. ``py/wikidata/docs/MAPPING.md`` explains *why* each column maps where it
does; this file is the executable form of that document.

Nothing here touches the network.
"""

from __future__ import annotations

import re

# -- the two obligatory statements -----------------------------------------
# Every chublet carries both. The class alone would also catch research
# software modelled by other communities; the WikiProject statement is what
# draws the boundary and makes the set retrievable as a set.
CHUBLET_CLASS = "Q141115627"
CHUBLET_WIKIPROJECT = "Q141169143"

# -- properties -------------------------------------------------------------
P_INSTANCE_OF = "P31"
P_MAINTAINED_BY_WIKIPROJECT = "P6104"
P_REPOSITORY = "P1324"
P_VERSION_CONTROL = "P8423"
P_ARCHIVE_URL = "P1065"
P_ARCHIVE_DATE = "P2960"
P_OFFICIAL_WEBSITE = "P856"
P_CRAN = "P5565"
P_PYPI = "P5568"
P_DOI = "P356"
P_PROGRAMMED_IN = "P277"
P_DEPENDS_ON = "P1547"
P_NAME = "P2561"
P_DESCRIBED_AT_URL = "P973"
P_EXACT_MATCH = "P2888"
P_MAIN_SUBJECT = "P921"

# What each property must be, checked by the ``check`` step against Wikidata.
# A property whose datatype has changed under us is the kind of thing that
# fails halfway through a batch rather than at the start.
EXPECTED_DATATYPES = {
    P_INSTANCE_OF: "wikibase-item",
    P_MAINTAINED_BY_WIKIPROJECT: "wikibase-item",
    P_REPOSITORY: "url",
    P_VERSION_CONTROL: "wikibase-item",
    P_ARCHIVE_URL: "url",
    P_ARCHIVE_DATE: "time",
    P_OFFICIAL_WEBSITE: "url",
    P_CRAN: "external-id",
    P_PYPI: "external-id",
    P_DOI: "external-id",
    P_PROGRAMMED_IN: "wikibase-item",
    P_DEPENDS_ON: "wikibase-item",
    P_NAME: "monolingualtext",
    P_DESCRIBED_AT_URL: "url",
    P_EXACT_MATCH: "url",
    P_MAIN_SUBJECT: "wikibase-item",
}

# Forge -> version control system. Bitbucket hosts both Git and Mercurial, so
# it stays empty and its repositories are reported rather than qualified.
FORGE_VCS = {
    "GitHub": "Git", "GitHub Gist": "Git", "GitLab": "Git", "Codeberg": "Git",
    "Launchpad": "Bazaar", "Bitbucket": "",
}

# Registry column -> (property, how to pull the package name out of the URL).
REGISTRY_PROPERTY = {
    "CRAN": (P_CRAN, r"package=([^/&?]+)"),
    "PyPI": (P_PYPI, r"pypi\.org/project/([^/?#]+)"),
}

# Sections of vocabulary.json and what each one feeds.
VOCABULARY_SECTIONS = {
    "version_control_system": f"value of {P_VERSION_CONTROL} on the repository statement",
    "programming_language": f"value of {P_PROGRAMMED_IN}, from platform_role = language",
    "host_application": f"value of {P_DEPENDS_ON}, from platform_role = host application",
    "deployment": f"refines {P_INSTANCE_OF}, from platform_role = deployment",
    "tag": f"value of {P_MAIN_SUBJECT}, one per open-archaeo tag",
    "item_class": f"second {P_INSTANCE_OF} value, one per open-archaeo category",
    "superclass": f"further {P_INSTANCE_OF} values applied to every item",
}

# The classes an entry gets beyond the chublet class, keyed by category. The
# Q-ids live in vocabulary.json and start out null, like every other controlled
# value -- the categories are known, the items they map to are a decision.
CATEGORY_CLASSES = ["Packages and libraries", "Standalone software", "Scripts"]

# Applied to every item regardless of category, e.g. research software. Also
# resolved through vocabulary.json.
SUPERCLASSES = ["research software"]

# Columns the concordance adds to the transformed table.
CONCORDANCE_EXTRA = [
    "qid", "match_property", "match_value", "wikidata_label",
    "is_chublet", "checked",
]


# Human-readable labels for the properties this import uses, so a preview can
# show "source code repository URL P1324" rather than a bare number. Kept here
# rather than fetched, so the preview works with no network at all.
PROPERTY_LABELS = {
    P_INSTANCE_OF: "instance of",
    P_MAINTAINED_BY_WIKIPROJECT: "maintained by WikiProject",
    P_REPOSITORY: "source code repository URL",
    P_VERSION_CONTROL: "version control system",
    P_ARCHIVE_URL: "archive URL",
    P_ARCHIVE_DATE: "archive date",
    P_OFFICIAL_WEBSITE: "official website",
    P_CRAN: "CRAN project",
    P_PYPI: "PyPI project",
    P_DOI: "DOI",
    P_PROGRAMMED_IN: "programmed in",
    P_DEPENDS_ON: "depends on software",
    P_NAME: "name",
    P_DESCRIBED_AT_URL: "described at URL",
    P_EXACT_MATCH: "exact match",
    P_MAIN_SUBJECT: "main subject",
}

# Where an external identifier resolves to, so the preview can link it the way
# Wikidata does rather than printing a bare string.
FORMATTER_URLS = {
    P_CRAN: "https://cran.r-project.org/package={}",
    P_PYPI: "https://pypi.org/project/{}/",
    P_DOI: "https://doi.org/{}",
}


class Claim:
    """One statement plus its qualifiers, independent of how it is written."""

    __slots__ = ("prop", "value", "datatype", "qualifiers", "note")

    def __init__(self, prop: str, value, datatype: str = "item",
                 qualifiers: list | None = None, note: str = "") -> None:
        self.prop = prop
        self.value = value
        self.datatype = datatype
        self.qualifiers = qualifiers or []
        self.note = note

    def __repr__(self) -> str:
        tail = "".join(f"  [{q.prop}={q.value}]" for q in self.qualifiers)
        return f"{self.prop} = {self.value} ({self.datatype}){tail}"


class Issue:
    """Something the import could not do, or did on purpose but differently.

    Three severities, and the difference between them is the whole point of the
    preview page:

    ``blocked``
        The import would produce something *wrong or invalid* -- a statement
        that violates a required-qualifier constraint, or an item that cannot
        be written at all. Red. These are bugs in the import or gaps that must
        be closed before writing.
    ``deferred``
        A value exists in open-archaeo and is deliberately not written here,
        either because it belongs on a different statement or because the Q-id
        it needs has not been chosen yet. Amber. Nothing is wrong; something is
        waiting.
    ``note``
        Neither of those: a remark about modelling that a reviewer should see
        once. Grey.
    """

    __slots__ = ("code", "severity", "message", "detail")

    BLOCKED = "blocked"
    DEFERRED = "deferred"
    NOTE = "note"

    def __init__(self, code: str, severity: str, message: str,
                 detail: str = "") -> None:
        self.code = code
        self.severity = severity
        self.message = message
        self.detail = detail

    def __repr__(self) -> str:
        return f"[{self.severity}] {self.message}"


# One line per issue code, shown in the legend of the preview page so that a
# reviewer can learn the taxonomy without reading this file.
ISSUE_LEGEND = {
    "no-vcs-qualifier": (
        Issue.BLOCKED,
        "P8423 is a required qualifier on P1324. A repository statement "
        "without it violates a constraint, and the value is derivable from "
        "the forge -- so this is a gap in the vocabulary, not in the data."),
    "unresolved-class": (
        Issue.BLOCKED,
        "The category has no Q-id yet, so the item would carry only the "
        "chublet class and nothing saying what kind of software it is."),
    "not-reconciled": (
        Issue.BLOCKED,
        "No Q-id, so push would skip the item entirely. Reconcile first, or "
        "enter one by hand."),
    "zenodo-doi": (
        Issue.DEFERRED,
        "A 10.5281 DOI is a Zenodo deposit: it identifies a release, not the "
        "tool. It belongs as a qualifier on P348 and would be wrong on the "
        "item, so it is left out until versions are modelled."),
    "archive-mismatch": (
        Issue.DEFERRED,
        "The Internet Archive snapshot is of a different forge than the "
        "repository recorded here -- the tool moved and the crawl did not "
        "follow. Attaching it would claim a copy that was never made."),
    "unresolved-language": (
        Issue.DEFERRED,
        "P277 needs an item for the programming language and none has been "
        "chosen yet."),
    "unresolved-host": (
        Issue.DEFERRED,
        "P1547 needs an item for the host application and none has been "
        "chosen yet."),
    "unresolved-tag": (
        Issue.DEFERRED,
        "P921 needs an item per subject term and this one has not been "
        "chosen yet."),
    "no-licence": (
        Issue.DEFERRED,
        "P1324 expects the item to state a licence and open-archaeo records "
        "none for any entry. It has to come from the repository, so every "
        "entry with code carries this."),
    "no-repository": (
        Issue.NOTE,
        "No repository URL, so the strongest reconciliation key is missing "
        "and fewer statements can be made."),
    "description-style": (
        Issue.NOTE,
        "Wikidata descriptions are lower case and carry no full stop. This "
        "one reads as a sentence and needs rewriting before it goes in."),
}

# A remark that applies to every item is a remark about the mapping, not about
# any item, so it belongs on the page once rather than in 208 grey boxes.
MODELLING_NOTES = [
    ("exact match rather than described at URL",
     "The open-archaeo entry is not a page that merely mentions the tool; it is "
     "a record of the same thing. P2888 exact match carries exactly that "
     "reading -- its equivalent property is skos:exactMatch and its "
     "unique-value constraint matches the one-entry-one-item relation -- so it "
     "is used for the entry page, and P973 described at URL is left for blog "
     "posts and videos, which describe without being the same thing. A "
     "dedicated open-archaeo identifier property, following the P6830 swMATH "
     "precedent, would be better still and is worth proposing."),
    ("classification beyond the chublet class",
     "Every item carries the chublet class and the WikiProject. Beyond those it "
     "should also say what kind of software it is, which is what the category "
     "column knows: one further P31 value per category, plus any superclass "
     "applied to all of them. Both come from vocabulary.json, so an unresolved "
     "category shows up as a blocked issue rather than as silence."),
]


IA_DATE = re.compile(r"_-_(\d{4})-(\d{2})-(\d{2})")
IA_SUBJECT = re.compile(r"/details/([^/?#]+?)_-_\d{4}-")


def package_name(url: str, pattern: str) -> str:
    match = re.search(pattern, url.strip())
    return match.group(1) if match else ""


def archive_date(url: str) -> str:
    """Extract the snapshot date embedded in an Internet Archive path.

    ``…/github.com-ISAAKiel-quantAAR_-_2020-07-09_13-14-14`` -> ``2020-07-09``.
    Day precision only: the time in the path is when the crawl ran, which is
    not a claim worth making to the second.
    """
    match = IA_DATE.search(url)
    return "-".join(match.groups()) if match else ""


def repository_key(url: str) -> str:
    """``https://github.com/ISAAKiel/quantAAR`` -> ``github.com-isaakiel-quantaar``."""
    stripped = re.sub(r"^https?://(www\.)?", "", url.strip()).rstrip("/")
    stripped = stripped[:-4] if stripped.endswith(".git") else stripped
    return stripped.replace("/", "-").lower()


def match_archive(repo_url: str, archives: list[str]) -> str:
    """Find the snapshot that belongs to this repository, if any.

    Fourteen entries list a Codeberg repository and a GitHub snapshot -- the
    tool moved, the crawl did not follow. Attaching that snapshot to the
    Codeberg statement would assert that the Internet Archive holds a copy of a
    repository it never saw, so the pairing is made on the path, not on order.
    """
    key = repository_key(repo_url)
    for archive in archives:
        subject = IA_SUBJECT.search(archive)
        if subject and subject.group(1).lower() == key:
            return archive
    return ""


def repository_variants(url: str) -> list[str]:
    """Spellings of a repository URL that Wikidata might hold instead.

    Wikidata records whatever the editor pasted. The same repository appears
    with and without a trailing slash, with and without ``.git``, and
    occasionally over http. Querying one spelling finds one of them.
    """
    url = url.strip()
    if not url:
        return []
    base = url.rstrip("/")
    base = base[:-4] if base.endswith(".git") else base
    variants = {base, base + "/", base + ".git"}
    if base.startswith("https://"):
        variants.add("http://" + base[len("https://"):])
    return sorted(variants)


def build_claims(row: dict, vocabulary: dict) -> tuple[list[Claim], list[Issue]]:
    """Turn one row into the statements it supports and the issues it raises.

    Returns both, because the second half is the interesting one: a value that
    is *not* written, and the reason it is not, is where a mapping decision
    becomes visible. Values that need a Q-id and do not have one are recorded
    as issues, never guessed -- an invented Q-id is a wrong statement that
    looks like a right one.
    """
    claims: list[Claim] = []
    issues: list[Issue] = []

    def raise_issue(code: str, detail: str = "") -> None:
        severity, message = ISSUE_LEGEND[code]
        issues.append(Issue(code, severity, message, detail))

    # -- classification ----------------------------------------------------
    # The chublet class and the WikiProject go on every item. Beyond them the
    # item should say what kind of software it is, which is what the category
    # column knows and the class alone does not.
    claims.append(Claim(P_INSTANCE_OF, CHUBLET_CLASS, note="obligatory"))
    for label in SUPERCLASSES:
        qid = vocabulary.get("superclass", {}).get(label)
        if qid:
            claims.append(Claim(P_INSTANCE_OF, qid, note=f"every item: {label}"))
    category_qid = vocabulary.get("item_class", {}).get(row["category"])
    if category_qid:
        claims.append(Claim(P_INSTANCE_OF, category_qid,
                            note=f"from category: {row['category']}"))
    else:
        raise_issue("unresolved-class", row["category"])
    claims.append(Claim(P_MAINTAINED_BY_WIKIPROJECT, CHUBLET_WIKIPROJECT,
                        note="obligatory"))

    if row["name"]:
        claims.append(Claim(P_NAME, row["name"], "monolingual@en"))

    # -- code --------------------------------------------------------------
    repos = [u for u in row["repository"].split("|") if u]
    hosts = [h for h in row["repository_host"].split("|") if h]
    archives = [u for u in row["internetarchive"].split("|") if u]
    if not repos:
        raise_issue("no-repository")
    for index, url in enumerate(repos):
        qualifiers: list[Claim] = []
        host = hosts[index] if index < len(hosts) else ""
        vcs_label = FORGE_VCS.get(host, "")
        vcs_qid = vocabulary.get("version_control_system", {}).get(vcs_label)
        if vcs_qid:
            qualifiers.append(Claim(P_VERSION_CONTROL, vcs_qid))
        else:
            raise_issue("no-vcs-qualifier", host or "unknown forge")
        archive = match_archive(url, archives)
        if archive:
            qualifiers.append(Claim(P_ARCHIVE_URL, archive, "url"))
            snapshot = archive_date(archive)
            if snapshot:
                qualifiers.append(Claim(P_ARCHIVE_DATE, snapshot, "time"))
        elif archives and index == 0:
            raise_issue("archive-mismatch", archives[0])
        claims.append(Claim(P_REPOSITORY, url, "url", qualifiers))
        if index == 0:
            raise_issue("no-licence")

    if row["website"]:
        claims.append(Claim(P_OFFICIAL_WEBSITE, row["website"], "url"))

    # -- registries and identifiers ---------------------------------------
    # registry and registry_name are parallel columns, so they are zipped
    # rather than compared as single values -- an entry may list both.
    for url, registry in zip(row["registry"].split("|"),
                             row["registry_name"].split("|")):
        if registry not in REGISTRY_PROPERTY:
            continue
        prop, pattern = REGISTRY_PROPERTY[registry]
        name = package_name(url, pattern)
        if name:
            claims.append(Claim(prop, name, "external-id"))

    if row["doi"]:
        if row["doi"].startswith("10.5281/"):
            raise_issue("zenodo-doi", row["doi"])
        else:
            claims.append(Claim(P_DOI, row["doi"].upper(), "external-id"))

    # -- what it is about --------------------------------------------------
    role, platform = row["platform_role"], row["platform"]
    if platform and role == "language":
        qid = vocabulary.get("programming_language", {}).get(platform)
        if qid:
            claims.append(Claim(P_PROGRAMMED_IN, qid))
        else:
            raise_issue("unresolved-language", platform)
    elif platform and role == "host application":
        qid = vocabulary.get("host_application", {}).get(platform)
        if qid:
            claims.append(Claim(P_DEPENDS_ON, qid))
        else:
            raise_issue("unresolved-host", platform)

    for tag in [t for t in row["tags"].split("|") if t]:
        qid = vocabulary.get("tag", {}).get(tag)
        if qid:
            claims.append(Claim(P_MAIN_SUBJECT, qid, note=f"tag: {tag}"))
        else:
            raise_issue("unresolved-tag", tag)

    # -- links -------------------------------------------------------------
    # The open-archaeo entry is not merely a page that mentions the tool; it is
    # a record *of* the tool. P2888 exact match carries exactly that reading --
    # its equivalent property is skos:exactMatch -- and its unique-value
    # constraint matches the one-entry-one-item relation. P973 is then free for
    # the pages that describe without being the same thing.
    if row["url"]:
        claims.append(Claim(P_EXACT_MATCH, row["url"], "url",
                            note="open-archaeo entry, same thing"))
    for column, what in (("blogpost", "blog post"), ("youtube", "video"),
                         ("publication", "publication")):
        for url in [u for u in row.get(column, "").split("|") if u]:
            if column == "publication" and url.startswith("10."):
                continue  # a bare DOI, not a URL
            claims.append(Claim(P_DESCRIBED_AT_URL, url, "url", note=what))

    if row["description"][:1].isupper() or row["description"].endswith("."):
        raise_issue("description-style", row["description"][:80])

    return claims, issues

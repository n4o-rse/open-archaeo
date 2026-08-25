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
    "tag": "value of P921, one per open-archaeo tag",
}

# Columns the concordance adds to the transformed table.
CONCORDANCE_EXTRA = [
    "qid", "match_property", "match_value", "wikidata_label",
    "is_chublet", "checked",
]


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


def build_claims(row: dict, vocabulary: dict,
                 skipped: list | None = None) -> list[Claim]:
    """Turn one concordance row into the statements it supports.

    Values that need a Q-id and do not have one are skipped and recorded, never
    guessed -- an invented Q-id is a wrong statement that looks like a right
    one.
    """
    skipped = skipped if skipped is not None else []
    claims: list[Claim] = [
        Claim(P_INSTANCE_OF, CHUBLET_CLASS, note="obligatory"),
        Claim(P_MAINTAINED_BY_WIKIPROJECT, CHUBLET_WIKIPROJECT, note="obligatory"),
    ]

    if row["name"]:
        claims.append(Claim(P_NAME, row["name"], "monolingual@en"))

    repos = [u for u in row["repository"].split("|") if u]
    hosts = [h for h in row["repository_host"].split("|") if h]
    archives = [u for u in row["internetarchive"].split("|") if u]
    for index, url in enumerate(repos):
        qualifiers: list[Claim] = []
        host = hosts[index] if index < len(hosts) else ""
        vcs_label = FORGE_VCS.get(host, "")
        vcs_qid = vocabulary["version_control_system"].get(vcs_label)
        if vcs_qid:
            qualifiers.append(Claim(P_VERSION_CONTROL, vcs_qid))
        else:
            skipped.append(f"{row['id']}: {P_VERSION_CONTROL} for host "
                           f"{host or '?'} -- required qualifier on {P_REPOSITORY}")
        archive = match_archive(url, archives)
        if archive:
            qualifiers.append(Claim(P_ARCHIVE_URL, archive, "url"))
            snapshot = archive_date(archive)
            if snapshot:
                qualifiers.append(Claim(P_ARCHIVE_DATE, snapshot, "time"))
        elif archives and index == 0:
            skipped.append(f"{row['id']}: archive snapshot matches no "
                           f"repository ({archives[0]})")
        claims.append(Claim(P_REPOSITORY, url, "url", qualifiers))

    if row["website"]:
        claims.append(Claim(P_OFFICIAL_WEBSITE, row["website"], "url"))

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

    # A Zenodo DOI identifies a release, not the tool, so it belongs on the
    # version statement. Until versions are modelled it is left out entirely
    # rather than asserted at item level, where it would be wrong.
    if row["doi"]:
        if row["doi"].startswith("10.5281/"):
            skipped.append(f"{row['id']}: {P_DOI} {row['doi']} is a Zenodo "
                           "deposit -- belongs on P348, not on the item")
        else:
            claims.append(Claim(P_DOI, row["doi"].upper(), "external-id"))

    role, platform = row["platform_role"], row["platform"]
    if platform and role == "language":
        qid = vocabulary["programming_language"].get(platform)
        if qid:
            claims.append(Claim(P_PROGRAMMED_IN, qid))
        else:
            skipped.append(f"{row['id']}: {P_PROGRAMMED_IN} for {platform}")
    elif platform and role == "host application":
        qid = vocabulary["host_application"].get(platform)
        if qid:
            claims.append(Claim(P_DEPENDS_ON, qid))
        else:
            skipped.append(f"{row['id']}: {P_DEPENDS_ON} for {platform}")

    if row["url"]:
        claims.append(Claim(P_DESCRIBED_AT_URL, row["url"], "url",
                            note="interim: no open-archaeo property exists yet"))
    return claims

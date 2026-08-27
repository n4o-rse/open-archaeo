#!/usr/bin/env python3
"""The step that runs first and writes nothing.

``check`` is the default action of ``main.py``: it exercises every part of the
route -- data, endpoints, identifiers, vocabulary, credentials, and the plan
itself -- without sending a single edit. What it is really checking is whether
``push --live`` would fail halfway through a batch, which is the expensive way
to find out.

Every check reports ok, warn or FAIL. Failures set the exit code; warnings do
not, because most of them describe work that is simply not done yet.
"""

from __future__ import annotations

import sys
from pathlib import Path

import labels as label_cache
import vocabulary as vocabulary_module
from api import WikidataClient, WikidataError, get_entities, read_credentials, sparql
from model import (
    EXPECTED_DATATYPES, IDENTITY_QIDS, IDENTITY_STATEMENTS, PROPERTY_LABELS,
    P_EXACT_MATCH, P_INVENTORY_NUMBER, build_claims,
)
from reconcile import CONCORDANCE_NAME, load_concordance

OK, WARN, FAIL = "ok  ", "warn", "FAIL"


class Report:
    """Collects the outcome of each check and prints it as it goes."""

    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def section(self, title: str) -> None:
        print(f"\n{title}")
        print("-" * len(title))

    def line(self, status: str, message: str) -> None:
        if status == FAIL:
            self.failures += 1
        elif status == WARN:
            self.warnings += 1
        print(f"  [{status}] {message}")

    def summary(self) -> int:
        print()
        if self.failures:
            print(f"{self.failures} failed, {self.warnings} warnings. "
                  "Fix the failures before running push --live.")
        elif self.warnings:
            print(f"All checks passed with {self.warnings} warnings. "
                  "The warnings describe work still to do, not defects.")
        else:
            print("All checks passed.")
        return 1 if self.failures else 0


# --------------------------------------------------------------------------

def check_data(report: Report, rows: list[dict]) -> None:
    report.section("Data")
    report.line(OK if rows else FAIL, f"{len(rows)} entries loaded and transformed")
    missing = [c for c in ("repository", "repository_host", "internetarchive",
                           "platform_role", "registry_name")
               if rows and c not in rows[0]]
    report.line(FAIL if missing else OK,
                f"derived columns present"
                + (f" -- missing: {', '.join(missing)}" if missing else ""))
    with_repo = sum(1 for r in rows if r["repository"])
    report.line(OK, f"{with_repo} entries carry a repository URL "
                    f"({len(rows) - with_repo} do not and cannot be matched on it)")


def check_endpoints(report: Report) -> bool:
    report.section("Endpoints")
    reachable = True
    try:
        sparql("SELECT ?x WHERE { BIND(1 AS ?x) }")
        report.line(OK, "query.wikidata.org answers")
    except WikidataError as exc:
        report.line(FAIL, f"query service unreachable: {exc}")
        reachable = False
    try:
        get_entities(["Q42"], props="info")
        report.line(OK, "www.wikidata.org/w/api.php answers")
    except WikidataError as exc:
        report.line(FAIL, f"Action API unreachable: {exc}")
        reachable = False
    return reachable


def check_entities(report: Report) -> None:
    """Every Q-id in the identity block must exist and be an item.

    Printing the label matters as much as the existence check: a Q-id that
    exists but names something else is the failure this catches, and only a
    person reading the label can catch it.
    """
    report.section("Obligatory identifiers")
    roles: dict[str, list[str]] = {}
    for prop, qid, _ in IDENTITY_STATEMENTS:
        roles.setdefault(qid, []).append(
            f"{prop} {PROPERTY_LABELS.get(prop, '')}".strip())
    try:
        entities = get_entities(IDENTITY_QIDS, props="info|labels|descriptions")
    except WikidataError as exc:
        report.line(FAIL, f"cannot read the identifiers: {exc}")
        return
    found: dict[str, str] = {}
    for qid in IDENTITY_QIDS:
        role = ", ".join(roles.get(qid, ["identity block"])) + " value"
        entity = entities.get(qid, {})
        if entity.get("missing") is not None or "id" not in entity:
            report.line(FAIL, f"{qid} ({role}) does not exist on Wikidata")
            continue
        label = entity.get("labels", {}).get("en", {}).get("value", "")
        found[qid] = label
        description = entity.get("descriptions", {}).get("en", {}).get("value", "")
        report.line(OK, f"{qid} ({role}) = {label or '(no English label)'}"
                        + (f" -- {description}" if description else ""))
    # These are the labels the preview needs, and this step has just read them
    # for free -- so the cache is filled here rather than by a second lookup.
    label_cache.update(found)


def check_labels(report: Report, vocab: dict | None) -> None:
    """Every resolved Q-id should have a cached label, so pages read as words.

    The identity block is handled above. What is left is whatever has been
    resolved in vocabulary.json since the last online run -- a Q-id set with
    'vocab --set' months ago has no reason to be in the cache, and a preview
    built offline then shows a bare number. This is the step that notices.
    """
    report.section("Labels")
    if vocab is None:
        report.line(WARN, "no vocabulary, so nothing to look up")
        return
    resolved = {qid for section, values in vocab.items()
                if not section.startswith("_") and isinstance(values, dict)
                for qid in values.values() if qid}
    if not resolved:
        report.line(OK, "no controlled value resolved yet")
        return
    cached = label_cache.load()
    missing = sorted(resolved - set(cached))
    if not missing:
        report.line(OK, f"{len(resolved)} resolved values, all named")
        return
    fresh = label_cache.resolve(missing, fetch=True)
    if fresh:
        report.line(OK, f"{len(fresh)} label(s) read and cached: "
                        + ", ".join(f"{q} {fresh[q]}" for q in sorted(fresh)[:5]))
    still = sorted(set(missing) - set(fresh))
    if still:
        report.line(WARN, f"{len(still)} resolved value(s) still unnamed, so "
                          "the preview shows numbers for them: "
                          + ", ".join(still[:5]))


def check_properties(report: Report) -> None:
    """Every property used must exist and still have the datatype assumed."""
    report.section("Properties and datatypes")
    try:
        entities = get_entities(sorted(EXPECTED_DATATYPES), props="info|datatype|labels")
    except WikidataError as exc:
        report.line(FAIL, f"cannot read the properties: {exc}")
        return
    for pid, expected in sorted(EXPECTED_DATATYPES.items()):
        entity = entities.get(pid, {})
        if entity.get("missing") is not None or "id" not in entity:
            report.line(FAIL, f"{pid} does not exist")
            continue
        actual = entity.get("datatype", "")
        label = entity.get("labels", {}).get("en", {}).get("value", "")
        if actual != expected:
            report.line(FAIL, f"{pid} ({label}) is {actual}, "
                              f"the model assumes {expected}")
        else:
            report.line(OK, f"{pid} {label} -- {actual}")


def check_concordance(report: Report, path: Path) -> list[dict]:
    report.section("Concordance")
    if not path.is_file():
        report.line(WARN, f"no concordance at {path} -- run reconcile first; "
                          "push has nothing to work on until then")
        return []
    rows = load_concordance(path)
    matched = [r for r in rows if r.get("qid")]
    tagged = [r for r in matched if r.get("is_chublet") == "yes"]
    manual = [r for r in matched if r.get("match_property") == "manual"]
    report.line(OK, f"{len(rows)} rows, {len(matched)} matched to a Q-id "
                    f"({len(manual)} of them by hand)")
    report.line(OK, f"{len(tagged)} already carry the whole identity block; "
                    f"{len(matched) - len(tagged)} matched but not yet tagged")
    stale = {r["checked"] for r in matched if r.get("checked")}
    if stale:
        report.line(OK, f"looked up on {', '.join(sorted(stale)[:3])}")
    duplicates = {q for q in (r["qid"] for r in matched)
                  if [r["qid"] for r in matched].count(q) > 1}
    report.line(FAIL if duplicates else OK,
                f"{len(duplicates)} Q-ids claimed by more than one entry"
                + (f": {', '.join(sorted(duplicates)[:5])}" if duplicates else ""))
    return rows


def check_vocabulary(report: Report, path: Path) -> dict | None:
    report.section("Vocabulary")
    if not path.is_file():
        report.line(WARN, f"no vocabulary at {path} -- run vocab first")
        return None
    vocab = vocabulary_module.load(path)
    open_by_section = vocabulary_module.unresolved(vocab)
    total = sum(len(vocab[s]) for s in open_by_section)
    still_open = sum(len(v) for v in open_by_section.values())
    report.line(OK, f"{total} controlled values, {total - still_open} resolved")
    for section, terms in open_by_section.items():
        if terms:
            preview = ", ".join(terms[:4])
            more = f" and {len(terms) - 4} more" if len(terms) > 4 else ""
            report.line(WARN, f"{section}: {len(terms)} unresolved -- "
                              f"{preview}{more}")
    return vocab


# The obligatory statements: the five item-valued ones plus P2888 and P217,
# which carry the slug. An item short of any of them is a defect in the
# mapping rather than a gap in the data.
IDENTITY_PROPERTIES = ({prop for prop, _, _ in IDENTITY_STATEMENTS}
                       | {P_EXACT_MATCH, P_INVENTORY_NUMBER})
IDENTITY_EXPECTED = len(IDENTITY_STATEMENTS) + 2


def check_plan(report: Report, rows: list[dict], vocab: dict | None) -> None:
    """Build every statement offline and report what push would do."""
    report.section("Plan")
    if not rows or vocab is None:
        report.line(WARN, "cannot build a plan without a concordance and a "
                          "vocabulary")
        return
    targets = [r for r in rows if r.get("qid")]
    if not targets:
        report.line(WARN, "no matched rows, so push would write nothing")
        return

    by_property: dict[str, int] = {}
    by_code: dict[str, tuple[str, int]] = {}
    qualifiers = 0
    thin: list[str] = []
    for row in targets:
        claims, issues = build_claims(row, vocab)
        obligatory = 0
        for claim in claims:
            by_property[claim.prop] = by_property.get(claim.prop, 0) + 1
            qualifiers += len(claim.qualifiers)
            if claim.prop in IDENTITY_PROPERTIES and \
                    claim.note.startswith("obligatory"):
                obligatory += 1
        if obligatory < IDENTITY_EXPECTED:
            thin.append(row["id"])
        for issue in issues:
            severity, count = by_code.get(issue.code, (issue.severity, 0))
            by_code[issue.code] = (severity, count + 1)
    total = sum(by_property.values())
    report.line(OK, f"{len(targets)} items, {total} statements, "
                    f"{qualifiers} qualifiers")

    report.line(FAIL if thin else OK,
                f"identity block complete on {len(targets) - len(thin)}/"
                f"{len(targets)} items"
                + (f" -- missing on {', '.join(thin[:5])}" if thin else ""))
    for prop, count in sorted(by_property.items(), key=lambda kv: -kv[1]):
        report.line(OK, f"  {prop}: {count}")
    for code, (severity, count) in sorted(by_code.items(),
                                          key=lambda kv: -kv[1][1]):
        report.line(FAIL if severity == "blocked" else WARN,
                    f"  {count} x {code} ({severity})")
    if by_code:
        report.line(OK, "run 'preview' to see these item by item")


def check_credentials(report: Report, config_path: Path, *,
                      do_login: bool = False) -> None:
    report.section("Credentials")
    username, password, agent, throttle = read_credentials(config_path)
    if not config_path.is_file():
        report.line(WARN, f"no {config_path.name} -- copy config.example.ini. "
                          "Only push --live needs it")
    if not username or not password:
        report.line(WARN, "no username or password set; push --live would stop")
    elif "@" not in username:
        report.line(WARN, f"{username} is not a bot password username "
                          "(expected 'Account@botname')")
    else:
        report.line(OK, f"bot password username {username}")
    if "contact" in agent:
        report.line(WARN, "User-Agent still carries the placeholder; push "
                          "refuses to run until it names a contact address")
    else:
        report.line(OK, f"User-Agent: {agent}")
    report.line(OK if throttle >= 0.5 else WARN,
                f"throttle {throttle}s between writes")

    if not do_login:
        report.line(OK, "not logging in (pass --login to test authentication)")
        return
    if not username or not password:
        report.line(FAIL, "--login given but no credentials available")
        return
    try:
        client = WikidataClient(username, password, user_agent=agent)
        who = client.login()
        info = client.whoami()
        report.line(OK, f"logged in as {who}")
        rights = set(info.get("rights", []))
        report.line(OK if "edit" in rights else FAIL,
                    "the account may edit" if "edit" in rights
                    else "the account has no edit right")
        report.line(OK if "bot" in rights else WARN,
                    "bot right present" if "bot" in rights
                    else "no bot right, so --mark-bot would fail")
        client.csrf()
        report.line(OK, "CSRF token obtained; no edit was made")
    except WikidataError as exc:
        report.line(FAIL, f"login failed: {exc}")


def run(*, rows: list[dict], concordance_path: Path, vocabulary_path: Path,
        config_path: Path, offline: bool = False, do_login: bool = False) -> int:
    """Run every check and return the exit code."""
    report = Report()
    print("Preflight for the open-archaeo -> Wikidata import. Nothing is written.")

    check_data(report, rows)
    if offline:
        report.section("Endpoints")
        report.line(WARN, "--offline: endpoints, identifiers and properties "
                          "not verified")
    elif check_endpoints(report):
        check_entities(report)
        check_properties(report)
    else:
        report.line(WARN, "skipping identifier and property checks")

    concordance = check_concordance(report, concordance_path)
    vocab = check_vocabulary(report, vocabulary_path)
    if not offline:
        check_labels(report, vocab)
    check_plan(report, concordance, vocab)
    check_credentials(report, config_path, do_login=do_login and not offline)

    return report.summary()

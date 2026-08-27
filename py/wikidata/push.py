#!/usr/bin/env python3
"""Write statements to Wikidata.

A dry run is the default and ``--live`` is the only way past it. This writes to
the live Wikidata, not to a private Wikibase, so the step is deliberately
conservative: it skips statements that already exist and refuses to start while
the User-Agent still carries its placeholder.

Creating items is a separate mode, ``--create``, and not the default, because
it is the only thing here that cannot be undone by editing: a duplicate has to
be merged, by a person, in a second pass. It refuses to run while any *other*
blocked issue stands, so an item is never created in a state that a preview
already called wrong.
"""

from __future__ import annotations

import sys
from pathlib import Path

from api import WikidataClient, WikidataError, read_credentials
from model import build_claims, description_for

# The one blocked issue that creating an item is the *answer* to, rather than a
# reason not to. Every other blocked issue means the item would be created
# wrong, and a wrong new item is worse than no item: it has to be found again
# before it can be fixed.
CREATION_EXEMPT = {"not-reconciled"}


def plan(rows: list[dict], vocab: dict, *, only: list[str] | None = None,
         limit: int = 0) -> tuple[list[tuple[dict, list]], list]:
    """Build the statements for every matched row, without contacting anything.

    Returns the plan and the issues raised across it. Blocked issues are the
    ones worth stopping for; see model.Issue.
    """
    targets = [r for r in rows if r.get("qid")]
    if only:
        wanted = set(only)
        targets = [r for r in targets if r["id"] in wanted or r["qid"] in wanted]
    if limit:
        targets = targets[:limit]
    plan_rows, issues = [], []
    for row in targets:
        claims, row_issues = build_claims(row, vocab)
        plan_rows.append((row, claims))
        issues.extend((row, issue) for issue in row_issues)
    return plan_rows, issues


def plan_creations(rows: list[dict], vocab: dict, *,
                   only: list[str] | None = None,
                   limit: int = 0) -> tuple[list[tuple[dict, list, str]], list]:
    """The rows with no Q-id, and the items they would become.

    Same shape as ``plan``, with the description each new item would carry.
    Nothing here contacts anything.
    """
    targets = [r for r in rows if not r.get("qid")]
    if only:
        wanted = set(only)
        targets = [r for r in targets if r["id"] in wanted]
    if limit:
        targets = targets[:limit]
    creations, issues = [], []
    for row in targets:
        claims, row_issues = build_claims(row, vocab)
        creations.append((row, claims, description_for(row)))
        issues.extend((row, issue) for issue in row_issues
                      if issue.code not in CREATION_EXEMPT)
    return creations, issues


def blocking(issues: list) -> list:
    """The issues that must be cleared before anything may be created."""
    return [(r, i) for r, i in issues if i.severity == "blocked"]


def show_creations(creations: list[tuple[dict, list, str]], issues: list,
                   *, show_skipped: int = 20) -> None:
    """Print the items that would be created, then what stands in the way."""
    for row, claims, description in creations[:show_skipped]:
        print(f"\n(new)  {row['name']}")
        print(f"    label (en)        {row['name']}")
        print(f"    description (en)  {description or '(none)'}")
        for claim in claims:
            suffix = f"   # {claim.note}" if claim.note else ""
            print(f"    {claim}{suffix}")
    if len(creations) > show_skipped:
        print(f"\n… and {len(creations) - show_skipped} more items")

    stopped = blocking(issues)
    if stopped:
        by_code: dict[str, int] = {}
        for _, issue in stopped:
            by_code[issue.code] = by_code.get(issue.code, 0) + 1
        print(f"\nBlocked -- these must be cleared before creating: "
              f"{len(stopped)}")
        for code, count in sorted(by_code.items(), key=lambda kv: -kv[1]):
            print(f"    {count} x {code}")
    missing = [row["name"] for row, _, description in creations
               if not description]
    if missing:
        print(f"\n{len(missing)} would be created without a description: "
              f"{', '.join(missing[:5])}")


def create(creations: list[tuple[dict, list, str]], *, config_path: Path,
           mark_bot: bool = False) -> tuple[int, int]:
    """Create the items and write the new Q-id back into each row.

    Returns (created, failed). The row is updated in place so the caller can
    save the concordance -- a created item whose Q-id is not recorded is a
    duplicate waiting to be made on the next run.
    """
    client = _client(config_path, mark_bot=mark_bot)
    created = failed = 0
    for row, claims, description in creations:
        try:
            qid = client.create_item(row["name"], description, claims)
        except WikidataError as error:
            failed += 1
            print(f"    FAILED {row['name']}: {error}", file=sys.stderr)
            continue
        row.update(qid=qid, match_property="created", match_value=row["slug"],
                   wikidata_label=row["name"], is_chublet="yes")
        created += 1
        print(f"{qid}  {row['name']}", file=sys.stderr)
    print(f"created {created}, failed {failed}", file=sys.stderr)
    return created, failed


def _client(config_path: Path, *, mark_bot: bool = False) -> WikidataClient:
    """Credentials, refusals, login. Shared by write() and create()."""
    username, password, agent, throttle = read_credentials(config_path)
    if not username or not password:
        sys.exit("error: no credentials. Set [wikidata] username/password in "
                 f"{config_path}, or WIKIDATA_USERNAME / WIKIDATA_PASSWORD.")
    if "contact" in agent:
        sys.exit("error: set a real user_agent with contact details in "
                 f"{config_path} before writing to Wikidata.")
    client = WikidataClient(username, password, user_agent=agent,
                            throttle=throttle, mark_bot=mark_bot)
    print(f"  logged in as {client.login()}", file=sys.stderr)
    return client


def show(plan_rows: list[tuple[dict, list]], issues: list,
         *, show_skipped: int = 20) -> None:
    """Print what would be written, then what was not and why."""
    for row, claims in plan_rows:
        print(f"\n{row['qid']}  {row['name']}")
        for claim in claims:
            suffix = f"   # {claim.note}" if claim.note else ""
            print(f"    {claim}{suffix}")

    blocked = [(r, i) for r, i in issues if i.severity == "blocked"]
    deferred = [(r, i) for r, i in issues if i.severity == "deferred"]
    for title, group in (("Blocked -- would be wrong or invalid", blocked),
                         ("Deferred -- a value exists but is not written here",
                          deferred)):
        if not group:
            continue
        print(f"\n{title}: {len(group)}")
        for row, issue in group[:show_skipped]:
            detail = f" ({issue.detail})" if issue.detail else ""
            print(f"    {row['id']} {issue.code}{detail}")
        if len(group) > show_skipped:
            print(f"    … and {len(group) - show_skipped} more")
    print("\nFor a readable version of all of this, run 'preview'.")


def write(plan_rows: list[tuple[dict, list]], *, config_path: Path,
          mark_bot: bool = False) -> int:
    """Write the planned statements. Returns the number of failures."""
    client = _client(config_path, mark_bot=mark_bot)

    written = existing = failed = 0
    for row, claims in plan_rows:
        print(f"{row['qid']}  {row['name']}", file=sys.stderr)
        for claim in claims:
            try:
                if client.claim_exists(row["qid"], claim):
                    existing += 1
                    continue
                claim_id = client.create_claim(row["qid"], claim)
                for qualifier in claim.qualifiers:
                    client.add_qualifier(claim_id, qualifier)
                written += 1
            except WikidataError as error:
                failed += 1
                print(f"    FAILED {claim.prop}: {error}", file=sys.stderr)
    print(f"written {written}, already present {existing}, failed {failed}",
          file=sys.stderr)
    return failed

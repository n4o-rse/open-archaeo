#!/usr/bin/env python3
"""Write statements to Wikidata.

A dry run is the default and ``--live`` is the only way past it. This writes to
the live Wikidata, not to a private Wikibase, so the step is deliberately
conservative: it never creates items, it skips statements that already exist,
and it refuses to start while the User-Agent still carries its placeholder.
"""

from __future__ import annotations

import sys
from pathlib import Path

from api import WikidataClient, WikidataError, read_credentials
from model import build_claims


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

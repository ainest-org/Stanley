"""Which work item a merge request belongs to, as GitLab itself expresses it: an issue reference
("Closes #12", "Related to #12", or just "#12") in the MR's title or description. Reconciliation
derives links from this, and Stanley's Link / Unlink buttons write the same references back to
GitLab, so the two never disagree.

An MR that references several issues is linked to all of them, and a work item can have many MRs.
"""

import re

# "#12" but not "group/project#12" or "abc#12"
ISSUE_REF = re.compile(r"(?<![\w/])#(\d+)\b")
CLOSING_REF = re.compile(r"\b(?:close[sd]?|closing|fix(?:e[sd])?|resolve[sd]?|implement(?:s|ed)?)\s+#(\d+)\b", re.I)


def referenced_issue_iids(title: str | None, description: str | None) -> list[str]:
    text = f"{title or ''}\n{description or ''}"
    ordered: list[str] = []
    for match in [*CLOSING_REF.finditer(text), *ISSUE_REF.finditer(text)]:
        iid = match.group(1)
        if iid not in ordered:
            ordered.append(iid)
    return ordered


def linked_work_item_ids(title: str | None, description: str | None, work_item_id_by_iid: dict) -> list:
    """Local ids of every referenced work item that exists in this project."""
    return [work_item_id_by_iid[iid] for iid in referenced_issue_iids(title, description) if iid in work_item_id_by_iid]


def add_reference(description: str | None, issue_iid: str, closes: bool) -> str:
    """Append "Closes #N" / "Related to #N" unless the description already references the issue."""
    current = description or ""
    if issue_iid in referenced_issue_iids(None, current):
        return current
    line = f"{'Closes' if closes else 'Related to'} #{issue_iid}"
    return f"{current.rstrip()}\n\n{line}".lstrip()


def remove_reference(description: str | None, issue_iid: str) -> str:
    """Drop whole lines that are just "<Closes|Fixes|Related to…> #N"; other mentions stay."""
    only_ref = re.compile(rf"^\s*(?:related to|closes?|fix(?:es)?|resolves?)\s+#{issue_iid}\s*$", re.I)
    kept = [line for line in (description or "").splitlines() if not only_ref.match(line)]
    return "\n".join(kept).strip()

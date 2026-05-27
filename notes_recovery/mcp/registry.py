from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from notes_recovery.services.case_protocol import (
    build_case_resource_lookup,
    discover_case_roots,
)

CASE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
DEMO_RESOURCE_MAP = {
    "case-tree": "demo_case_tree",
    "verification-summary": "demo_verification_summary",
    "operator-brief": "demo_operator_brief",
    "ai-triage-summary": "ai_triage_summary",
}


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    root_dir: Path


class CaseRegistry:
    def __init__(self, records: list[CaseRecord]) -> None:
        self._records = {record.case_id: record for record in records}

    @classmethod
    def build(cls, case_dirs: Iterable[Path], cases_roots: Iterable[Path]) -> "CaseRegistry":
        roots = discover_case_roots(case_dirs=case_dirs, search_roots=cases_roots)
        name_counts: dict[str, int] = {}
        for root in roots:
            name_counts[root.name] = name_counts.get(root.name, 0) + 1
        records: list[CaseRecord] = []
        for root in roots:
            safe_name = CASE_ID_RE.sub("-", root.name).strip("-") or "case"
            if name_counts[root.name] > 1:
                digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:8]
                case_id = f"{safe_name}--{digest}"
            else:
                case_id = safe_name
            records.append(CaseRecord(case_id=case_id, root_dir=root))
        return cls(records)

    def list(self) -> list[CaseRecord]:
        return sorted(self._records.values(), key=lambda item: item.case_id)

    def require(self, case_id: str) -> CaseRecord:
        record = self._records.get(case_id)
        if record is None:
            raise ValueError(f"Unknown case id: {case_id}")
        return record


def read_resource_text(case_root: Path, source_id: str) -> str:
    lookup = build_case_resource_lookup(case_root, include_ai_review=True)
    if source_id not in lookup:
        raise ValueError(f"Resource is not available for this case: {source_id}")
    return lookup[source_id].content


__all__ = [
    "CASE_ID_RE",
    "DEMO_RESOURCE_MAP",
    "CaseRecord",
    "CaseRegistry",
    "read_resource_text",
]

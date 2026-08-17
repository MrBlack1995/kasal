#!/usr/bin/env python
"""Run the UCMV Re-evaluation sweep from the CLI (no crew needed).

Finds previously-untranslatable DAX measures that TODAY's transpiler can recover,
by replaying stored conversion history. Read-only: it proposes candidates and never
modifies metric views.

Usage (from src/backend/, so the venv + src package resolve):

    # what capability level are we at?
    .venv/bin/python ../../scripts/ucmv_reevaluate.py --capability

    # sweep every dataset stored for a group
    .venv/bin/python ../../scripts/ucmv_reevaluate.py --group-id bi-specialist

    # specific datasets, and force a retry even if the fingerprint is unchanged
    .venv/bin/python ../../scripts/ucmv_reevaluate.py --group-id g --datasets ds1,ds2 --force

    # also allow the LLM path (COSTS TOKENS)
    .venv/bin/python ../../scripts/ucmv_reevaluate.py --group-id g --use-llm

Docs: src/docs/powerbi/ucmv-reevaluation-recoverable-measures.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Make the backend's `src` package importable no matter which directory this is
# invoked from (repo root, scripts/, or src/backend/).
_BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "src", "backend")
if os.path.isdir(os.path.join(_BACKEND, "src")) and _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def main() -> int:
    p = argparse.ArgumentParser(description="UCMV re-evaluation sweep (read-only).")
    p.add_argument("--group-id", default=None, help="Group/tenant to scope stored runs.")
    p.add_argument("--datasets", default=None,
                   help="Comma-separated PBI dataset ids (default: all for the group).")
    p.add_argument("--force", action="store_true",
                   help="Retry even when the capability fingerprint is unchanged.")
    p.add_argument("--use-llm", action="store_true",
                   help="Allow the LLM-first path (COSTS TOKENS per measure).")
    p.add_argument("--include-impossible", action="store_true",
                   help="Also retry permanent-limitation categories (usually wasted).")
    p.add_argument("--max-measures", type=int, default=200,
                   help="Cap retried measures per dataset (default 200).")
    p.add_argument("--max-datasets", type=int, default=50,
                   help="Cap datasets scanned (default 50).")
    p.add_argument("--capability", action="store_true",
                   help="Just print the current capability fingerprint and exit.")
    p.add_argument("--json", action="store_true", help="Print the raw JSON report.")
    args = p.parse_args()

    from src.engines.crewai.tools.custom.metric_view_utils.capability_version import (
        capability_summary,
    )

    if args.capability:
        summary = capability_summary()
        print(f"capability fingerprint : {summary['fingerprint']}")
        print(f"translator patterns    : {summary['pattern_count']}")
        print(f"skill corpus files     : {summary['skill_file_count']}")
        for f in summary["skill_files"]:
            print(f"    - {f}")
        return 0

    if not args.group_id and not args.datasets:
        p.error("give --group-id and/or --datasets (nothing to scan otherwise)")

    from src.engines.crewai.tools.custom.ucmv_reevaluation_tool import UCMVReevaluationTool

    tool = UCMVReevaluationTool()
    raw = tool._run(
        group_id=args.group_id,
        dataset_ids=args.datasets,
        force=args.force,
        use_llm=args.use_llm,
        include_impossible=args.include_impossible,
        max_measures_per_dataset=args.max_measures,
        max_datasets=args.max_datasets,
    )

    if args.json:
        print(raw)
        return 0

    report = json.loads(raw)
    if report.get("error"):
        print(f"ERROR: {report['error']}", file=sys.stderr)
        return 1

    cap = report.get("capability", {})
    summary = report.get("summary", {})
    print(f"\ncapability {cap.get('fingerprint')} "
          f"({cap.get('pattern_count')} patterns, {cap.get('skill_file_count')} skill files)")
    print(f"settings   {report.get('settings')}")
    print(f"\nscanned {summary.get('datasets_scanned', 0)} dataset(s) | "
          f"retried {summary.get('measures_retried', 0)} measure(s) | "
          f"RECOVERABLE {summary.get('measures_recovered', 0)}\n")

    for ds in report.get("datasets", []):
        items = ds.get("newly_translatable") or []
        head = f"  {ds.get('dataset_id') or '(unknown)'}"
        if items:
            print(f"{head}  → {len(items)} recoverable")
            for m in items:
                print(f"      {m['original_name']}  (used by {m.get('referenced_by', 0)})")
                print(f"        was : {m.get('previous_category')} — {m.get('previous_skip_reason')}")
                print(f"        now : {m['new_sql']}")
        else:
            note = ds.get("note") or "no gains"
            print(f"{head}  → {note}")

    if not summary.get("measures_recovered"):
        print("\nNothing recoverable. If you expected gains, try --force (the stored run "
              "may already be at the current capability level).")
    else:
        print("\nNothing was changed. Re-run the UCMV generator for the affected "
              "dataset(s) to apply these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

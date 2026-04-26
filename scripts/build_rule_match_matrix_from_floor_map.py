#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


STATUS_PRIORITY = {
    "matched": 0,
    "needs_measurement": 1,
    "needs_refined_detection": 2,
    "partially_matched": 3,
    "not_primary": 4,
    "not_applicable": 5,
    "unseen": 6,
}


def choose_status(statuses: list[str]) -> str:
    ranked = sorted(statuses, key=lambda item: STATUS_PRIORITY.get(item, 999))
    return ranked[0] if ranked else "unseen"


def main() -> None:
    source_dir = Path(
        "/Users/halu/Desktop/codex/commercial_diagnoser/data/source_ingest/huishan_tod_0409"
    )
    floor_map_path = source_dir / "rule_match_by_floor.v1.json"
    rule_library_path = Path(
        "/Users/halu/Desktop/codex/commercial_diagnoser/data/rules/longfor/longfor_foundation_rules_all.json"
    )
    output_path = source_dir / "rule_match_matrix.v2.json"

    floor_map = json.loads(floor_map_path.read_text())
    rules = json.loads(rule_library_path.read_text())

    by_rule: dict[str, dict] = {}
    for rule in rules:
        by_rule[rule["rule_id"]] = {
            "rule_id": rule["rule_id"],
            "title": rule["title"],
            "source_type": rule["source_type"],
            "category_l1": rule["category_l1"],
            "category_l2": rule["category_l2"],
            "status_candidates": [],
            "related_pages": [],
            "by_floor": [],
        }

    for floor in floor_map["floors"]:
        for match in floor["rule_matches"]:
            rule_bucket = by_rule[match["rule_id"]]
            rule_bucket["status_candidates"].append(match["status"])
            rule_bucket["related_pages"].append(floor["page_index"])
            rule_bucket["by_floor"].append(
                {
                    "page_index": floor["page_index"],
                    "page_label": floor["page_label"],
                    "status": match["status"],
                    "reason": match["reason"],
                }
            )

    matches = []
    for rule_id, rule_bucket in by_rule.items():
        global_status = choose_status(rule_bucket["status_candidates"])
        matches.append(
            {
                "rule_id": rule_id,
                "title": rule_bucket["title"],
                "source_type": rule_bucket["source_type"],
                "category_l1": rule_bucket["category_l1"],
                "category_l2": rule_bucket["category_l2"],
                "status": global_status,
                "related_pages": sorted(set(rule_bucket["related_pages"])),
                "by_floor": rule_bucket["by_floor"],
            }
        )

    result = {
        "sample_id": floor_map["document_id"],
        "project_name": floor_map["project_name"],
        "rule_library_path": str(rule_library_path),
        "source_floor_map_path": str(floor_map_path),
        "matches": matches,
    }

    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "rule_count": len(matches),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

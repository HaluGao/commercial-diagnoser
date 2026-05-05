from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMAL_RULES_PATH = ROOT / "data" / "rules" / "longfor" / "longfor_foundation_rules_all.json"
C2_REVIEW_BASE_PATH = ROOT / "data" / "rules" / "review" / "c2_incremental" / "c2_incremental_review_base_library.json"
OUTPUT_PATH = ROOT / "data" / "rules" / "longfor" / "longfor_complete_rule_library_v1.json"
SUMMARY_PATH = ROOT / "data" / "rules" / "longfor" / "longfor_complete_rule_library_v1.summary.json"


def rule_signature(rule: dict) -> str:
    text = str(rule.get("rule_text") or rule.get("title") or "")
    category = str(rule.get("category_l1") or "")
    compact = re.sub(r"\s+", "", text).lower()
    return f"{category}::{compact}"


def main() -> None:
    formal_rules = json.loads(FORMAL_RULES_PATH.read_text())
    review_data = json.loads(C2_REVIEW_BASE_PATH.read_text())
    review_rules = review_data["rules"] if isinstance(review_data, dict) else review_data

    merged: list[dict] = []
    seen: set[str] = set()
    duplicate_count = 0

    for rule in formal_rules:
        item = dict(rule)
        item.setdefault("source_label", "正式基础规则库")
        item["library_role"] = "formal_foundation"
        item["library_version"] = "longfor-complete-rule-library-v1"
        signature = rule_signature(item)
        if signature in seen:
            duplicate_count += 1
            continue
        seen.add(signature)
        merged.append(item)

    for rule in review_rules:
        item = dict(rule)
        item.setdefault("source_label", "龙湖C2天街产品包（完整抽取）")
        item["library_role"] = "c2_complete_rule"
        item["library_version"] = "longfor-complete-rule-library-v1"
        signature = rule_signature(item)
        if signature in seen:
            duplicate_count += 1
            continue
        seen.add(signature)
        merged.append(item)

    category_breakdown: dict[str, int] = {}
    source_breakdown: dict[str, int] = {}
    for rule in merged:
        category = rule.get("category_l1", "未分类")
        source = rule.get("source_label", "unknown")
        category_breakdown[category] = category_breakdown.get(category, 0) + 1
        source_breakdown[source] = source_breakdown.get(source, 0) + 1

    payload = {
        "library_id": "longfor-complete-rule-library-v1",
        "library_name": "龙湖商业咨询完整规则库 V1",
        "version": "2026-05-05",
        "description": "基于最新版龙湖C2天街产品包全量抽取结果，并合并当前正式基础规则后的单一完整规则库。",
        "source_scope": [
            "龙湖C2天街产品包（完整版，全量图片抽取）",
            "当前正式基础规则库（含2024天街建标与已精修规则）",
        ],
        "total_rule_count": len(merged),
        "formal_rule_count": len(formal_rules),
        "c2_complete_rule_count": len(review_rules),
        "deduplicated_overlap_count": duplicate_count,
        "category_breakdown": category_breakdown,
        "source_breakdown": source_breakdown,
        "rules": merged,
    }

    summary = {
        "library_id": payload["library_id"],
        "library_name": payload["library_name"],
        "version": payload["version"],
        "total_rule_count": payload["total_rule_count"],
        "formal_rule_count": payload["formal_rule_count"],
        "c2_complete_rule_count": payload["c2_complete_rule_count"],
        "deduplicated_overlap_count": payload["deduplicated_overlap_count"],
        "category_breakdown": payload["category_breakdown"],
        "source_breakdown": payload["source_breakdown"],
    }

    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    print(f"complete_rules={len(merged)} duplicates={duplicate_count}")


if __name__ == "__main__":
    main()

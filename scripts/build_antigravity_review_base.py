#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path


IMPORTED_PATH = Path(
    "/Users/halu/Desktop/codex/commercial_diagnoser/data/rules/imported/antigravity/antigravity_rule_candidates.normalized.json"
)
FORMAL_PATH = Path(
    "/Users/halu/Desktop/codex/commercial_diagnoser/data/rules/longfor/longfor_foundation_rules_all.json"
)
OUTPUT_DIR = Path(
    "/Users/halu/Desktop/codex/commercial_diagnoser/data/rules/review/antigravity"
)
REVIEW_BASE_PATH = OUTPUT_DIR / "antigravity_review_base_library.json"
SUMMARY_PATH = OUTPUT_DIR / "antigravity_review_base_summary.json"
QUEUE_PATH = OUTPUT_DIR / "antigravity_review_priority_queue.json"
REVIEW_MD_PATH = OUTPUT_DIR / "antigravity_review_base_overview.md"

GENERIC_TARGET_HINTS = [
    "天街",
    "购物中心",
    "商业",
    "地下商业层",
    "地下一层",
    "首层",
    "二层",
    "餐饮多经",
    "区域级购物中心",
    "mall",
]
PROJECT_SPECIFIC_HINTS = [
    "大渡口",
    "重庆",
    "成都",
    "西安",
    "上海",
    "杭州",
    "宁波",
    "长沙",
    "惠山",
    "项目",
    "公园",
    "广场",
    "街区",
]


def compact(text: str) -> str:
    return re.sub(r"[\s，。；：、“”‘’（）()【】\\-_/]+", "", text).lower()


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, compact(left), compact(right)).ratio()


def pick_best_formal_match(candidate: dict, formal_rules: list[dict]) -> tuple[str | None, float]:
    candidate_text = " ".join(
        filter(
            None,
            [
                str(candidate.get("normalized_text") or ""),
                str(candidate.get("rule_desc") or ""),
                str(candidate.get("raw_metric") or ""),
                str(candidate.get("raw_value") or ""),
            ],
        )
    )
    best_rule_id: str | None = None
    best_score = 0.0

    for formal in formal_rules:
        formal_text = " ".join(
            filter(
                None,
                [
                    str(formal.get("title") or ""),
                    str(formal.get("rule_text") or ""),
                    str(formal.get("interpretation") or ""),
                ],
            )
        )
        score = similarity(candidate_text, formal_text)
        if score > best_score:
            best_score = score
            best_rule_id = formal.get("rule_id")

    return best_rule_id, best_score


def is_case_specific_example(candidate: dict) -> bool:
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ["raw_target", "raw_metric", "raw_value", "rule_desc"]
    )
    target = str(candidate.get("raw_target") or "")
    has_specific_name = any(hint in text for hint in PROJECT_SPECIFIC_HINTS)
    target_is_generic = any(hint in target for hint in GENERIC_TARGET_HINTS)
    exact_metric_fact = bool(
        re.search(r"\d", text)
        and any(
            metric in str(candidate.get("raw_metric") or "")
            for metric in ["高程", "面积", "高差", "总面积", "单层面积", "进深", "宽度"]
        )
    )
    return exact_metric_fact or (has_specific_name and target and not target_is_generic)


def needs_manual_split(candidate: dict) -> bool:
    text = str(candidate.get("rule_desc") or "")
    return sum(text.count(sep) for sep in ["；", ";", "、"]) >= 2 and len(text) > 36


def build_review_record(candidate: dict, formal_rules: list[dict]) -> dict:
    best_rule_id, best_score = pick_best_formal_match(candidate, formal_rules)
    category_l1 = candidate.get("mapped_category_l1") or "待人工归类"
    category_l2 = candidate.get("raw_metric") or candidate.get("raw_target") or "导入候选项"
    normalized_text = candidate.get("normalized_text") or candidate.get("rule_desc") or "未命名候选规则"
    title = (candidate.get("rule_desc") or normalized_text)[:40]

    review_bucket = "candidate_rule"
    merge_recommendation = "candidate_for_foundation_merge"
    confidence_score = 0.72
    duplicate_of_rule_id = None
    review_notes = [
        "该条目由 Antigravity 导入并完成首轮自动复核，尚未经过逐条人工定稿。",
    ]

    if category_l1 == "待人工归类":
        review_bucket = "needs_category_refine"
        merge_recommendation = "keep_in_review_base"
        confidence_score = 0.45
        review_notes.append("一级分类仍为“待人工归类”，需在并入正式库前补齐章节归属。")

    if is_case_specific_example(candidate):
        review_bucket = "case_specific_example"
        merge_recommendation = "hold_as_reference_only"
        confidence_score = min(confidence_score, 0.42)
        review_notes.append("条目更像案例事实或项目参数，不宜直接作为通用底线规则并入正式库。")

    if needs_manual_split(candidate):
        review_bucket = "needs_manual_split"
        merge_recommendation = "keep_in_review_base"
        confidence_score = min(confidence_score, 0.5)
        review_notes.append("该条目可能混合了多个判断点，建议后续拆成更原子的规则。")

    if best_score >= 0.58:
        review_bucket = "near_duplicate_formal"
        merge_recommendation = "hold_as_reference_only"
        confidence_score = min(confidence_score, 0.66)
        duplicate_of_rule_id = best_rule_id
        review_notes.append(
            f"与当前正式规则库中的 `{best_rule_id}` 存在较高表述相似度，建议先视为近重复候选。"
        )

    interpretation_parts = [
        f"原始分类：{candidate.get('raw_category')}" if candidate.get("raw_category") else None,
        f"原始指标：{candidate.get('raw_metric')}" if candidate.get("raw_metric") else None,
        f"原始取值：{candidate.get('raw_value')}" if candidate.get("raw_value") else None,
        candidate.get("rule_desc"),
    ]
    interpretation = "；".join(part for part in interpretation_parts if part)

    return {
        "rule_id": f"LF-AGR-REVIEW-{candidate['import_id']}",
        "title": title,
        "source_type": "imported_antigravity",
        "source_file": candidate.get("source_file"),
        "source_locator": {
            "page": None,
            "image_name": candidate.get("source_image"),
            "region_hint": "Antigravity 导入候选规则首轮复核条目",
        },
        "category_l1": category_l1,
        "category_l2": category_l2,
        "tags": [
            item
            for item in [
                candidate.get("raw_category"),
                candidate.get("raw_metric"),
                candidate.get("raw_target"),
            ]
            if item
        ],
        "applicable_asset_types": ["mall"],
        "judgement_type": "heuristic",
        "severity_default": "medium",
        "rule_text": normalized_text,
        "interpretation": interpretation,
        "evidence_requirement": "需结合原始 C2 图片页和后续正式规则编制结果复核，不应直接作为唯一裁决依据。",
        "diagnosis_targets": [],
        "trigger_clues": [],
        "output_template": {
            "issue_title_hint": "基于导入候选规则的待确认诊断点",
            "issue_body_hint": "该条目可作为顾问式判断的参考，但需结合正式规则与图纸证据复核。",
            "recommendation_hint": "建议继续核对原始图片页，并判断是否应并入正式基础规则库。"
        },
        "source_excerpt": candidate.get("rule_desc"),
        "notes": candidate.get("notes"),
        "review_status": "auto_screened",
        "review_bucket": review_bucket,
        "merge_recommendation": merge_recommendation,
        "confidence_score": round(confidence_score, 2),
        "duplicate_of_rule_id": duplicate_of_rule_id,
        "lineage": {
            "import_id": candidate.get("import_id"),
            "source_system": candidate.get("source_system"),
            "candidate_status": candidate.get("candidate_status"),
        },
        "review_notes": review_notes,
    }


def build_priority_queue(review_base: list[dict]) -> list[dict]:
    priority_order = {
        "candidate_for_foundation_merge": 0,
        "keep_in_review_base": 1,
        "hold_as_reference_only": 2,
        "reject_from_library": 3,
    }
    sorted_rules = sorted(
        review_base,
        key=lambda item: (
            priority_order.get(item["merge_recommendation"], 9),
            item["review_bucket"],
            -item["confidence_score"],
            item["rule_id"],
        ),
    )
    queue = []
    for idx, item in enumerate(sorted_rules, start=1):
        queue.append(
            {
                "priority_rank": idx,
                "rule_id": item["rule_id"],
                "title": item["title"],
                "category_l1": item["category_l1"],
                "review_bucket": item["review_bucket"],
                "merge_recommendation": item["merge_recommendation"],
                "confidence_score": item["confidence_score"],
                "duplicate_of_rule_id": item["duplicate_of_rule_id"],
            }
        )
    return queue


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    imported_rules = json.loads(IMPORTED_PATH.read_text())
    formal_rules = json.loads(FORMAL_PATH.read_text())

    review_base = [build_review_record(item, formal_rules) for item in imported_rules]
    priority_queue = build_priority_queue(review_base)

    bucket_counts = Counter(item["review_bucket"] for item in review_base)
    merge_counts = Counter(item["merge_recommendation"] for item in review_base)
    category_counts = Counter(item["category_l1"] for item in review_base)

    summary = {
        "input_imported_rule_count": len(imported_rules),
        "formal_rule_count": len(formal_rules),
        "review_base_count": len(review_base),
        "review_status_counts": Counter(item["review_status"] for item in review_base),
        "review_bucket_counts": dict(sorted(bucket_counts.items())),
        "merge_recommendation_counts": dict(sorted(merge_counts.items())),
        "category_l1_counts": dict(sorted(category_counts.items())),
        "note": "这是 569 条导入候选规则的首轮自动复核底库，不等同于逐条人工定稿后的正式基础规则库。",
    }

    REVIEW_BASE_PATH.write_text(json.dumps(review_base, ensure_ascii=False, indent=2) + "\n")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    QUEUE_PATH.write_text(json.dumps(priority_queue, ensure_ascii=False, indent=2) + "\n")

    md_lines = [
        "# Antigravity 569条候选规则首轮复核概览",
        "",
        f"- 导入候选规则总数：`{len(imported_rules)}`",
        f"- 当前正式规则总数：`{len(formal_rules)}`",
        f"- 首轮复核底库条目：`{len(review_base)}`",
        "",
        "## 复核分桶",
        "",
    ]
    for key, value in sorted(bucket_counts.items()):
        md_lines.append(f"- `{key}`: `{value}`")
    md_lines.extend(["", "## 并库建议", ""])
    for key, value in sorted(merge_counts.items()):
        md_lines.append(f"- `{key}`: `{value}`")
    md_lines.extend(["", "## 一级分类分布", ""])
    for key, value in sorted(category_counts.items()):
        md_lines.append(f"- `{key}`: `{value}`")
    md_lines.extend(
        [
            "",
            "## 当前结论",
            "",
            "- 这份文件是“复核工作底库”，目的是把 569 条导入候选规则全部写入统一底层结构，并给出后续人工复核顺序。",
            "- 其中 `candidate_for_foundation_merge` 可优先进入下一轮逐条精修，准备并入正式基础规则库。",
            "- `hold_as_reference_only` 多为近重复表述或案例事实，不建议直接写成正式底线规则。",
            "- `needs_category_refine` 与 `needs_manual_split` 是下一轮最值得优先清理的两类。",
            "",
            "## 关键文件",
            "",
            f"- [review base]({REVIEW_BASE_PATH})",
            f"- [summary]({SUMMARY_PATH})",
            f"- [priority queue]({QUEUE_PATH})",
        ]
    )
    REVIEW_MD_PATH.write_text("\n".join(md_lines) + "\n")

    print(
        json.dumps(
            {
                "review_base_path": str(REVIEW_BASE_PATH),
                "summary_path": str(SUMMARY_PATH),
                "queue_path": str(QUEUE_PATH),
                "review_base_count": len(review_base),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

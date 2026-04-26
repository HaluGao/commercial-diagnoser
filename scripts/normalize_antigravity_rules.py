#!/usr/bin/env python3

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


RAW_PATH = Path(
    "/Users/halu/Desktop/codex/commercial_diagnoser/imports/antigravity_snapshot/extracted_rules.raw.json"
)
OUTPUT_DIR = Path(
    "/Users/halu/Desktop/codex/commercial_diagnoser/data/rules/imported/antigravity"
)
NORMALIZED_PATH = OUTPUT_DIR / "antigravity_rule_candidates.normalized.json"
SUMMARY_PATH = OUTPUT_DIR / "antigravity_rule_candidates.summary.json"


def map_category(category: str) -> str:
    text = category or ""
    if any(key in text for key in ["财务", "NPI", "COST", "坪效", "生意逻辑", "开发目标"]):
        return "总纲与价值逻辑"
    if any(key in text for key in ["TOD", "地铁", "地下", "下沉", "接驳"]):
        return "TOD与地下商业"
    if any(key in text for key in ["到达", "入口", "落客", "步行", "车行"]):
        return "到达与交通组织"
    if any(key in text for key in ["动线", "客流", "扶梯", "洞口", "走道", "中庭"]):
        return "动线与客流分发"
    if any(key in text for key in ["影院", "超市", "多经", "租客", "铺位", "业态", "主力店"]):
        return "租户落位与铺位效率"
    if any(key in text for key in ["停车", "层高", "消防", "卫生间", "设备", "建造标准"]):
        return "建造标准与安全底线"
    if any(key in text for key in ["立面", "幕墙", "基座", "转角", "材质", "产品表达"]):
        return "产品表达与建筑形象"
    if "精装" in text:
        return "精装场景"
    if any(key in text for key in ["景观", "露台", "外街", "内街", "屋顶", "庭院"]):
        return "景观场景与铺前界面"
    if any(key in text for key in ["空间", "场景", "面积", "楼层功能"]):
        return "空间布局与体验场景"
    if any(key in text for key in ["规划", "策略"]):
        return "整体定位与规划逻辑"
    return "待人工归类"


def build_normalized_text(item: dict) -> str:
    parts = []
    if item.get("target"):
        parts.append(f"对象：{item['target']}")
    if item.get("metric"):
        parts.append(f"指标：{item['metric']}")
    if item.get("value"):
        parts.append(f"目标值：{item['value']}")
    if item.get("rule_desc"):
        parts.append(f"规则：{item['rule_desc']}")
    return "；".join(parts)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_rules = json.loads(RAW_PATH.read_text())

    normalized_rules = []
    mapped_counter = Counter()
    source_image_counter = Counter()

    for idx, item in enumerate(raw_rules, start=1):
        mapped_category = map_category(item.get("category", ""))
        mapped_counter[mapped_category] += 1
        source_image_counter[item.get("source_image", "<missing>")] += 1

        normalized_rules.append(
            {
                "import_id": f"AGR-{idx:04d}",
                "source_system": "antigravity_demo",
                "source_file": "extracted_rules.raw.json",
                "source_image": item.get("source_image"),
                "candidate_status": "imported_raw_candidate",
                "raw_category": item.get("category"),
                "raw_target": item.get("target"),
                "raw_metric": item.get("metric"),
                "raw_value": item.get("value"),
                "rule_desc": item.get("rule_desc"),
                "mapped_category_l1": mapped_category,
                "normalized_text": build_normalized_text(item),
                "notes": "由 Antigravity demo 的 extracted_rules.json 导入，尚未纳入 codex 基础规则库。"
            }
        )

    NORMALIZED_PATH.write_text(
        json.dumps(normalized_rules, ensure_ascii=False, indent=2) + "\n"
    )

    summary = {
        "source_system": "antigravity_demo",
        "source_file": str(RAW_PATH),
        "normalized_output": str(NORMALIZED_PATH),
        "rule_count": len(normalized_rules),
        "mapped_category_counts": dict(sorted(mapped_counter.items())),
        "top_source_images": source_image_counter.most_common(20),
        "note": "该文件是导入候选规则摘要，不等同于 codex 当前正式基础规则库。",
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    print(
        json.dumps(
            {
                "normalized_output": str(NORMALIZED_PATH),
                "summary_output": str(SUMMARY_PATH),
                "rule_count": len(normalized_rules),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

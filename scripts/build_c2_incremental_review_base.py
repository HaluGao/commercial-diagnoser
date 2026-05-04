#!/usr/bin/env python3

from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_PATH = BASE_DIR / 'data' / 'rules' / 'imported' / 'c2_incremental' / 'c2_incremental_extracted_rules.raw.json'
FORMAL_PATH = BASE_DIR / 'data' / 'rules' / 'longfor' / 'longfor_foundation_rules_all.json'
OUTPUT_DIR = BASE_DIR / 'data' / 'rules' / 'review' / 'c2_incremental'
REVIEW_BASE_PATH = OUTPUT_DIR / 'c2_incremental_review_base_library.json'
SUMMARY_PATH = OUTPUT_DIR / 'c2_incremental_review_base_summary.json'
QUEUE_PATH = OUTPUT_DIR / 'c2_incremental_review_priority_queue.json'
OVERVIEW_PATH = OUTPUT_DIR / 'c2_incremental_review_base_overview.md'

CATEGORY_HINTS = {
    '整体定位与规划逻辑': ['规划', '定位', '骨架', '连接', '策略', '交通', '到达'],
    '动线与客流分发': ['动线', '扶梯', '到达', '客流', '分发', '连接'],
    '租户落位与铺位效率': ['铺位', '店', '影院', '超市', '主力', '餐饮'],
    '空间布局与体验场景': ['场景', '体验', '中庭', '空间', '界面', '节点'],
    '建造标准与安全底线': ['消防', '建造', '净高', '宽度', '高差', '疏散'],
    'TOD与地下商业': ['tod', '地下', 'b1', '地下一层'],
    '产品表达与建筑形象': ['形象', '立面', '界面', '展示'],
}


def compact(text: str) -> str:
    return re.sub(r"[\s，。；：、“”‘’（）()【】\-_/]+", "", text).lower()


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, compact(left), compact(right)).ratio()


def map_category_l1(item: dict) -> str:
    bundle = ' '.join(str(item.get(k) or '') for k in ['category', 'target', 'metric', 'rule_desc']).lower()
    for category, hints in CATEGORY_HINTS.items():
        if any(h.lower() in bundle for h in hints):
            return category
    return '待人工归类'


def build_rule_text(item: dict) -> str:
    return str(item.get('rule_desc') or '').strip()


def pick_best_formal_match(rule_text: str, formal_rules: list[dict]) -> tuple[str | None, float]:
    best_rule_id = None
    best_score = 0.0
    for formal in formal_rules:
        formal_text = ' '.join(
            filter(None, [
                str(formal.get('title') or ''),
                str(formal.get('rule_text') or ''),
                str(formal.get('interpretation') or ''),
            ])
        )
        score = similarity(rule_text, formal_text)
        if score > best_score:
            best_score = score
            best_rule_id = formal.get('rule_id')
    return best_rule_id, best_score


def build_record(index: int, item: dict, formal_rules: list[dict]) -> dict:
    rule_text = build_rule_text(item)
    best_rule_id, best_score = pick_best_formal_match(rule_text, formal_rules)
    category_l1 = map_category_l1(item)
    category_l2 = str(item.get('metric') or item.get('target') or '导入候选项')
    merge_recommendation = 'candidate_for_foundation_merge'
    review_bucket = 'candidate_rule'
    confidence_score = 0.76
    duplicate_of_rule_id = None
    notes = ['该条目由新版 C2 图片自动抽取，尚未进入逐条人工定稿。']

    if category_l1 == '待人工归类':
        merge_recommendation = 'keep_in_review_base'
        review_bucket = 'needs_category_refine'
        confidence_score = 0.5
        notes.append('一级分类仍需人工细化。')

    if best_score >= 0.62:
        merge_recommendation = 'hold_as_reference_only'
        review_bucket = 'near_duplicate_formal'
        confidence_score = min(confidence_score, 0.68)
        duplicate_of_rule_id = best_rule_id
        notes.append(f'与正式规则 `{best_rule_id}` 表述相近，建议先作为近重复参考。')

    interpretation_parts = [
        f"原始分类：{item.get('category')}" if item.get('category') else None,
        f"原始对象：{item.get('target')}" if item.get('target') else None,
        f"原始指标：{item.get('metric')}" if item.get('metric') else None,
        f"原始取值：{item.get('value')}" if item.get('value') else None,
        rule_text,
    ]

    return {
        'rule_id': f'LF-C2-INC-REVIEW-{index:04d}',
        'title': (rule_text or f"{item.get('category')}-{item.get('target')}")[:40],
        'source_type': 'longfor_c2_incremental',
        'source_file': item.get('source_image'),
        'source_locator': {
            'page': None,
            'image_name': item.get('source_image'),
            'region_hint': '新版龙湖C2天街产品包整页自动抽取',
        },
        'category_l1': category_l1,
        'category_l2': category_l2,
        'tags': [tag for tag in [item.get('category'), item.get('target'), item.get('metric')] if tag],
        'applicable_asset_types': ['mall', 'mixed_use'],
        'judgement_type': 'heuristic',
        'severity_default': 'medium',
        'rule_text': rule_text,
        'interpretation': '；'.join(part for part in interpretation_parts if part),
        'evidence_requirement': '需结合原始 C2 图片页和后续正式规则编制结果复核，不应直接作为唯一裁决依据。',
        'diagnosis_targets': [],
        'trigger_clues': [],
        'output_template': {
            'issue_title_hint': '基于 C2 图片抽取的待确认诊断点',
            'issue_body_hint': '该条目可作为顾问式判断的参考，但需结合正式规则与图纸证据复核。',
            'recommendation_hint': '建议继续核对原始 C2 图片页，并判断是否应并入正式基础规则库。'
        },
        'source_excerpt': rule_text,
        'notes': f"source_value={item.get('value')}",
        'review_status': 'auto_screened',
        'review_bucket': review_bucket,
        'merge_recommendation': merge_recommendation,
        'confidence_score': round(confidence_score, 2),
        'duplicate_of_rule_id': duplicate_of_rule_id,
        'lineage': {
            'source_image': item.get('source_image'),
            'raw_category': item.get('category'),
            'raw_target': item.get('target'),
            'raw_metric': item.get('metric'),
            'raw_value': item.get('value'),
        },
        'review_notes': notes,
    }


def build_priority_queue(review_base: list[dict]) -> list[dict]:
    priority_order = {
        'candidate_for_foundation_merge': 0,
        'keep_in_review_base': 1,
        'hold_as_reference_only': 2,
    }
    sorted_rules = sorted(
        review_base,
        key=lambda item: (
            priority_order.get(item['merge_recommendation'], 9),
            item['review_bucket'],
            -item['confidence_score'],
            item['rule_id'],
        ),
    )
    queue = []
    for idx, item in enumerate(sorted_rules, start=1):
        queue.append({
            'priority_rank': idx,
            'rule_id': item['rule_id'],
            'title': item['title'],
            'category_l1': item['category_l1'],
            'review_bucket': item['review_bucket'],
            'merge_recommendation': item['merge_recommendation'],
            'confidence_score': item['confidence_score'],
            'duplicate_of_rule_id': item['duplicate_of_rule_id'],
        })
    return queue


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_rules = json.loads(RAW_PATH.read_text()) if RAW_PATH.exists() else []
    formal_rules = json.loads(FORMAL_PATH.read_text())
    review_base = [build_record(idx, item, formal_rules) for idx, item in enumerate(raw_rules, start=1)]
    queue = build_priority_queue(review_base)

    REVIEW_BASE_PATH.write_text(json.dumps(review_base, ensure_ascii=False, indent=2) + '\n')
    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + '\n')

    summary = {
        'input_incremental_rule_count': len(raw_rules),
        'formal_rule_count': len(formal_rules),
        'review_base_count': len(review_base),
        'review_bucket_counts': dict(Counter(item['review_bucket'] for item in review_base)),
        'merge_recommendation_counts': dict(Counter(item['merge_recommendation'] for item in review_base)),
        'category_l1_counts': dict(Counter(item['category_l1'] for item in review_base)),
        'note': '这是新版 C2 图片自动抽取规则的首轮复核底库，不等同于逐条人工定稿后的正式基础规则库。',
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')

    lines = [
        '# 新版C2增量规则首轮复核概览',
        '',
        f"- 导入候选规则总数：`{len(raw_rules)}`",
        f"- 当前正式规则总数：`{len(formal_rules)}`",
        f"- 首轮复核底库条目：`{len(review_base)}`",
        '',
        '## 复核分桶',
        '',
    ]
    for key, value in summary['review_bucket_counts'].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(['', '## 并库建议', ''])
    for key, value in summary['merge_recommendation_counts'].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(['', '## 一级分类分布', ''])
    for key, value in summary['category_l1_counts'].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend([
        '',
        '## 当前结论',
        '',
        '- 这份文件是“新版 C2 图片抽取规则”的复核工作底库，目的是把当前已抽取条目写入统一底层结构，并给出后续人工复核顺序。',
        '- 其中 `candidate_for_foundation_merge` 可优先进入下一轮逐条精修，准备并入正式基础规则库。',
        '- `hold_as_reference_only` 多为与现有正式规则近重复的表述，不建议直接重复写入正式库。',
        '- `needs_category_refine` 是下一轮最值得优先清理的条目。',
    ])
    OVERVIEW_PATH.write_text('\n'.join(lines) + '\n')

    print(json.dumps({
        'review_base_count': len(review_base),
        'summary_path': str(SUMMARY_PATH),
        'review_base_path': str(REVIEW_BASE_PATH),
        'queue_path': str(QUEUE_PATH),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

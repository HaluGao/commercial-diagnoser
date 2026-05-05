#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_PATH = BASE_DIR / 'data' / 'rules' / 'imported' / 'tianjie_standard_2024' / 'tianjie_standard_2024_extracted_rules.raw.json'
OUTPUT_DIR = BASE_DIR / 'data' / 'rules' / 'review' / 'tianjie_standard_2024'
REVIEW_BASE_PATH = OUTPUT_DIR / 'tianjie_standard_2024_review_base_library.json'
SUMMARY_PATH = OUTPUT_DIR / 'tianjie_standard_2024_review_base_summary.json'
QUEUE_PATH = OUTPUT_DIR / 'tianjie_standard_2024_review_priority_queue.json'
OVERVIEW_PATH = OUTPUT_DIR / 'tianjie_standard_2024_review_base_overview.md'

CATEGORY_HINTS = {
    '建造标准与安全底线': ['净高', '宽度', '服务半径', '面积', '比例', '消防', '疏散', '设备机房', '卫生间', '自动扶梯', '坡扶梯', '客梯', '货梯', '防火', '结构'],
    '到达与交通组织': ['公交', '落客', '接驳', '轨道交通', '出租车', '停车', '车位', '车行', '人行'],
    '产品表达与建筑形象': ['立面', '广告位', '标识', '形象', '材质', '照明', '发光', '外立面', '幕墙'],
    '空间布局与体验场景': ['中庭', '界面', '空间', '节点', '体验', '场景'],
    '租户落位与铺位效率': ['商铺', '影院', '餐饮', '店铺', '面宽', '进深', '后勤', '卸货'],
    '动线与客流分发': ['动线', '扶梯', '连通', '通道', '分发', '步行'],
    'TOD与地下商业': ['地下', 'tod', 'b1', '地下一层'],
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


def build_record(index: int, item: dict) -> dict:
    rule_text = build_rule_text(item)
    category_l1 = map_category_l1(item)
    category_l2 = str(item.get('metric') or item.get('target') or '建标候选项')
    merge_recommendation = 'candidate_for_foundation_merge'
    review_bucket = 'technical_control_rule'
    confidence_score = 0.86
    notes = ['该条目由龙湖天街建标-2024版图片自动抽取，偏技术性和强控性，可优先进入正式规则库精修。']

    if category_l1 == '待人工归类':
        merge_recommendation = 'keep_in_review_base'
        review_bucket = 'needs_category_refine'
        confidence_score = 0.58
        notes.append('一级分类仍需人工细化。')

    interpretation_parts = [
        f"原始分类：{item.get('category')}" if item.get('category') else None,
        f"原始对象：{item.get('target')}" if item.get('target') else None,
        f"原始指标：{item.get('metric')}" if item.get('metric') else None,
        f"原始取值：{item.get('value')}" if item.get('value') else None,
        rule_text,
    ]

    return {
        'rule_id': f'LF-TJBZ-2024-REVIEW-{index:04d}',
        'title': (rule_text or f"{item.get('category')}-{item.get('target')}")[:60],
        'source_type': 'longfor_tianjie_standard_2024',
        'source_label': '龙湖天街建标-2024版',
        'source_file': item.get('source_image'),
        'source_locator': {
            'page': None,
            'image_name': item.get('source_image'),
            'region_hint': '龙湖天街建标-2024版整页自动抽取',
        },
        'category_l1': category_l1,
        'category_l2': category_l2,
        'tags': [tag for tag in [item.get('category'), item.get('target'), item.get('metric')] if tag],
        'applicable_asset_types': ['mall', 'mixed_use'],
        'judgement_type': 'hard_rule' if category_l1 in {'建造标准与安全底线', '产品表达与建筑形象', '到达与交通组织'} else 'heuristic',
        'severity_default': 'high' if category_l1 in {'建造标准与安全底线', '产品表达与建筑形象'} else 'medium',
        'rule_text': rule_text,
        'interpretation': '；'.join(part for part in interpretation_parts if part),
        'evidence_requirement': '需结合龙湖天街建标-2024版原始页及方案图纸核对，可作为较强判断依据。',
        'diagnosis_targets': [],
        'trigger_clues': [],
        'output_template': {
            'issue_title_hint': '基于天街建标的技术控制项',
            'issue_body_hint': '该条目具有较强技术性和控制性，可直接作为方案诊断依据之一。',
            'recommendation_hint': '建议对照建标原始页与方案图纸进一步核验，并纳入正式规则库。'
        },
        'source_excerpt': rule_text,
        'notes': f"source_value={item.get('value')}",
        'review_status': 'auto_screened',
        'review_bucket': review_bucket,
        'merge_recommendation': merge_recommendation,
        'confidence_score': round(confidence_score, 2),
        'duplicate_of_rule_id': None,
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
    return [
        {
            'priority_rank': idx,
            'rule_id': item['rule_id'],
            'title': item['title'],
            'category_l1': item['category_l1'],
            'review_bucket': item['review_bucket'],
            'merge_recommendation': item['merge_recommendation'],
            'confidence_score': item['confidence_score'],
        }
        for idx, item in enumerate(sorted_rules, start=1)
    ]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_rules = json.loads(RAW_PATH.read_text()) if RAW_PATH.exists() else []
    review_base = [build_record(idx, item) for idx, item in enumerate(raw_rules, start=1)]
    queue = build_priority_queue(review_base)

    REVIEW_BASE_PATH.write_text(json.dumps(review_base, ensure_ascii=False, indent=2) + '\n')
    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + '\n')

    summary = {
        'input_rule_count': len(raw_rules),
        'review_base_count': len(review_base),
        'review_bucket_counts': dict(Counter(item['review_bucket'] for item in review_base)),
        'merge_recommendation_counts': dict(Counter(item['merge_recommendation'] for item in review_base)),
        'category_l1_counts': dict(Counter(item['category_l1'] for item in review_base)),
        'note': '这是龙湖天街建标-2024版图片自动抽取规则的首轮复核底库，偏技术性和强控性。',
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')

    lines = [
        '# 龙湖天街建标-2024版首轮复核概览',
        '',
        f"- 导入候选规则总数：`{len(raw_rules)}`",
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
    OVERVIEW_PATH.write_text('\n'.join(lines) + '\n')

    print(json.dumps({
        'review_base_count': len(review_base),
        'summary_path': str(SUMMARY_PATH),
        'review_base_path': str(REVIEW_BASE_PATH),
        'queue_path': str(QUEUE_PATH),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

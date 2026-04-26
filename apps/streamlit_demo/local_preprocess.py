from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import fitz


FOUNDATION_RULES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "rules" / "longfor" / "longfor_foundation_rules_all.json"
)
IMPORTED_RULES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "rules" / "imported" / "antigravity" / "antigravity_rule_candidates.normalized.json"
)
REVIEW_BASE_RULES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "rules" / "review" / "antigravity" / "antigravity_review_base_library.json"
)

FORMAL_ONLY = "formal_only"
IMPORTED_ONLY = "imported_only"
MERGED_ALL = "merged_all"


def load_rule_library(mode: str = FORMAL_ONLY) -> dict[str, Any]:
    formal_rules = json.loads(FOUNDATION_RULES_PATH.read_text())
    if REVIEW_BASE_RULES_PATH.exists():
        imported_rules = json.loads(REVIEW_BASE_RULES_PATH.read_text())
    else:
        imported_raw_rules = json.loads(IMPORTED_RULES_PATH.read_text())
        imported_rules = [_normalize_imported_rule(rule) for rule in imported_raw_rules]

    if mode == IMPORTED_ONLY:
        selected_rules = imported_rules
    elif mode == MERGED_ALL:
        selected_rules = _deduplicate_rules(formal_rules + imported_rules)
    else:
        selected_rules = formal_rules

    return {
        "rules": selected_rules,
        "summary": _build_rule_summary(
            mode=mode,
            formal_rules=formal_rules,
            imported_rules=imported_rules,
            selected_rules=selected_rules,
        ),
    }


def build_rule_context(rules: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for rule in rules:
        l1 = rule.get("category_l1", "未分类")
        l2 = rule.get("category_l2", "未分类")
        grouped.setdefault(l1, {}).setdefault(l2, []).append(
            {
                "rule_id": rule.get("rule_id"),
                "title": rule.get("title"),
                "judgement_type": rule.get("judgement_type"),
                "severity_default": rule.get("severity_default"),
                "rule_text": rule.get("rule_text"),
                "interpretation": rule.get("interpretation"),
                "source_label": rule.get("source_label"),
            }
        )
    return grouped


def preprocess_inputs(uploaded_files, camera_photo) -> dict[str, Any]:
    media_items: list[dict[str, str]] = []
    file_summaries: list[dict[str, Any]] = []
    text_snippets: list[str] = []

    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.getvalue()
            if uploaded_file.type == "application/pdf":
                pdf_summary = _preprocess_pdf(uploaded_file.name, file_bytes)
                media_items.extend(pdf_summary["media_items"])
                file_summaries.append(pdf_summary["file_summary"])
                text_snippets.extend(pdf_summary["text_snippets"])
            elif uploaded_file.type.startswith("image"):
                media_items.append(
                    {
                        "mime_type": uploaded_file.type or "image/jpeg",
                        "data": base64.b64encode(file_bytes).decode("utf-8"),
                    }
                )
                file_summaries.append(
                    {
                        "file_name": uploaded_file.name,
                        "file_type": uploaded_file.type,
                        "page_count": 1,
                        "notes": "图片文件，直接进入多模态分析。",
                    }
                )

    if camera_photo:
        camera_bytes = camera_photo.getvalue()
        media_items.append(
            {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(camera_bytes).decode("utf-8"),
            }
        )
        file_summaries.append(
            {
                "file_name": camera_photo.name or "camera_capture.jpg",
                "file_type": "image/jpeg",
                "page_count": 1,
                "notes": "现场拍照文件，直接进入多模态分析。",
            }
        )

    text_snippets = [snippet for snippet in text_snippets if snippet.strip()][:20]

    return {
        "media_items": media_items[:20],
        "file_summaries": file_summaries,
        "text_snippets": text_snippets,
    }


def build_analysis_prompt(preprocessed: dict[str, Any], rules: list[dict[str, Any]]) -> str:
    rule_context = json.dumps(build_rule_context(rules), ensure_ascii=False, indent=2)
    file_context = json.dumps(preprocessed["file_summaries"], ensure_ascii=False, indent=2)
    text_context = json.dumps(preprocessed["text_snippets"], ensure_ascii=False, indent=2)

    return f"""
你是一个严谨、克制、专业的商业建筑方案 AI 诊断顾问。

你的任务是基于本地预处理结果、上传的图纸图像，以及内置基础规则库，对商业建筑方案做第一轮顾问式诊断。

【重要要求】
1. 当前诊断对象可能包含 PDF 拆页后的平面图、总平、立面图片或现场实拍图片。
2. 你必须优先输出“框架性诊断”，不要把未量化的内容直接写成已违规。
3. 对能明确确认的问题，可写为“错误指出意见”；对需要进一步量化或深化的事项，写为“高优先级复核项”或“优化建议”。
4. 每条意见都要尽量指出对应的页层、图纸类型或空间部位。
5. 语气采用顾问式，不要夸奖，不要空泛。

【本地预处理结果：文件摘要】
{file_context}

【本地预处理结果：抽取到的文本片段】
{text_context}

【内置基础规则库】
{rule_context}

【输出格式】
请直接输出 Markdown，结构固定为：

## 总体判断
## 框架性优势
## 框架性风险
## 错误指出意见
## 优化性意见
## 下一轮建议重点复核专题
## 依据索引

不要输出总标题，不要写“项目诊断草稿”“诊断草稿”“草稿版”“Draft”等抬头。
直接从“## 总体判断”开始输出。

【错误指出意见】与【优化性意见】下的每一条，尽量包含：
- 标题
- 判断级别
- 对应部位
- 主要依据
- 说明
- 建议

如果某些内容证据不足，请明确写“需进一步量化/识别”，不要伪造尺寸或参数。
""".strip()


def _normalize_imported_rule(rule: dict[str, Any]) -> dict[str, Any]:
    category_l1 = rule.get("mapped_category_l1") or rule.get("raw_category") or "导入候选规则"
    source_image = rule.get("source_image") or "unknown"
    normalized_text = (
        rule.get("normalized_text")
        or rule.get("rule_desc")
        or rule.get("raw_metric")
        or rule.get("raw_category")
        or "未命名候选规则"
    )
    title = normalized_text[:48]

    interpretation_parts = [
        part
        for part in [
            rule.get("rule_desc"),
            f"原始分类：{rule['raw_category']}" if rule.get("raw_category") else None,
            f"原始指标：{rule['raw_metric']}" if rule.get("raw_metric") else None,
            f"原始取值：{rule['raw_value']}" if rule.get("raw_value") else None,
            "该条目来自 Antigravity 导入候选规则，尚未完成正式校核。"
            if rule.get("candidate_status") == "imported_raw_candidate"
            else None,
        ]
        if part
    ]

    return {
        "rule_id": rule.get("import_id"),
        "title": title,
        "source_type": "imported_antigravity_candidate",
        "source_label": "Antigravity 导入候选规则",
        "source_file": rule.get("source_file"),
        "source_locator": {
            "page": None,
            "image_name": source_image,
            "region_hint": "导入候选规则条目",
        },
        "category_l1": category_l1,
        "category_l2": rule.get("raw_metric") or rule.get("raw_target") or "导入候选项",
        "tags": [item for item in [rule.get("raw_category"), rule.get("raw_metric"), rule.get("raw_target")] if item],
        "applicable_asset_types": ["mall"],
        "judgement_type": "candidate_reference",
        "severity_default": "medium",
        "rule_text": normalized_text,
        "interpretation": "；".join(interpretation_parts),
        "evidence_requirement": "需要结合正式规则和图纸继续复核，不可单独作为硬性违规结论依据。",
        "diagnosis_targets": [],
        "trigger_clues": [],
        "output_template": {
            "statement_style": "consulting",
            "use_as": "reference_or_hypothesis",
        },
        "source_excerpt": rule.get("rule_desc"),
        "notes": rule.get("notes"),
    }


def _deduplicate_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()

    for rule in rules:
        signature = _rule_signature(rule)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        deduped.append(rule)

    return deduped


def _rule_signature(rule: dict[str, Any]) -> str:
    text = str(rule.get("rule_text") or rule.get("normalized_text") or rule.get("title") or "")
    category = str(rule.get("category_l1") or "")
    compact_text = re.sub(r"\s+", "", text).lower()
    return f"{category}::{compact_text}"


def _build_rule_summary(
    mode: str,
    formal_rules: list[dict[str, Any]],
    imported_rules: list[dict[str, Any]],
    selected_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    for rule in selected_rules:
        source_label = rule.get("source_label") or rule.get("source_type") or "unknown"
        source_counts[source_label] = source_counts.get(source_label, 0) + 1

    return {
        "mode": mode,
        "formal_rule_count": len(formal_rules),
        "imported_candidate_count": len(imported_rules),
        "selected_rule_count": len(selected_rules),
        "source_breakdown": source_counts,
    }


def _preprocess_pdf(file_name: str, file_bytes: bytes) -> dict[str, Any]:
    document = fitz.open(stream=file_bytes, filetype="pdf")
    media_items: list[dict[str, str]] = []
    text_snippets: list[str] = []

    for page_index in range(min(len(document), 12)):
        page = document.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        image_bytes = pix.tobytes("jpeg")
        media_items.append(
            {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(image_bytes).decode("utf-8"),
            }
        )

        raw_text = page.get_text("text").strip()
        if raw_text:
            compact_text = " ".join(raw_text.split())
            text_snippets.append(
                f"第{page_index + 1}页：{compact_text[:500]}"
            )

    return {
        "media_items": media_items,
        "text_snippets": text_snippets,
        "file_summary": {
            "file_name": file_name,
            "file_type": "application/pdf",
            "page_count": len(document),
            "notes": "PDF 已在本地拆页为图像，并抽取基础文本片段。",
        },
    }

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import fitz


COMPLETE_RULES_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "rules"
    / "longfor"
    / "longfor_complete_rule_library_v2.json"
)

FIVE_DIMENSION_INDEX_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "rules"
    / "longfor"
    / "longfor_complete_rule_library_v2.five_dimension_index.json"
)

FIVE_DIMENSIONS = ["大规划", "大交通", "大连接", "大骨架", "大场景"]


def load_rule_library() -> dict[str, Any]:
    library = json.loads(COMPLETE_RULES_PATH.read_text())
    five_dimension_index = json.loads(FIVE_DIMENSION_INDEX_PATH.read_text())
    rules = library.get("rules", [])
    summary = {
        "library_id": library.get("library_id"),
        "library_name": library.get("library_name"),
        "version": library.get("version"),
        "total_rule_count": library.get("total_rule_count", len(rules)),
        "formal_rule_count": library.get("formal_rule_count", 0),
        "c2_complete_rule_count": library.get("c2_complete_rule_count", 0),
        "deduplicated_overlap_count": library.get("deduplicated_overlap_count", 0),
        "category_breakdown": library.get("category_breakdown", {}),
        "source_breakdown": library.get("source_breakdown", {}),
    }
    return {
        "rules": rules,
        "summary": summary,
        "five_dimension_index": five_dimension_index.get("items", []),
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


def build_five_dimension_rule_context(
    rules: list[dict[str, Any]],
    five_dimension_index: list[dict[str, Any]],
    per_dimension: int = 14,
) -> dict[str, list[dict[str, Any]]]:
    rule_by_id = {rule.get("rule_id"): rule for rule in rules}
    items_by_dimension: dict[str, list[dict[str, Any]]] = {dimension: [] for dimension in FIVE_DIMENSIONS}

    confidence_rank = {"high": 0, "medium": 1, "low": 2}
    role_rank = {
        "formal_foundation": 0,
        "tianjie_technical_rule": 1,
        "c2_complete_rule": 2,
    }

    eligible_items = [
        item
        for item in five_dimension_index
        if item.get("primary_dimension") in FIVE_DIMENSIONS
        and item.get("confidence") in {"high", "medium"}
    ]
    eligible_items.sort(
        key=lambda item: (
            item.get("primary_dimension", ""),
            confidence_rank.get(item.get("confidence"), 9),
            role_rank.get(item.get("library_role"), 9),
            item.get("rule_id") or "",
        )
    )

    for item in eligible_items:
        dimension = item.get("primary_dimension")
        if not dimension or len(items_by_dimension[dimension]) >= per_dimension:
            continue
        rule = rule_by_id.get(item.get("rule_id"))
        if not rule:
            continue
        items_by_dimension[dimension].append(
            {
                "rule_id": rule.get("rule_id"),
                "title": rule.get("title"),
                "dimension": dimension,
                "secondary_dimensions": item.get("secondary_dimensions", []),
                "confidence": item.get("confidence"),
                "category_l1": rule.get("category_l1"),
                "category_l2": rule.get("category_l2"),
                "severity_default": rule.get("severity_default"),
                "rule_text": _clip(rule.get("rule_text", ""), 220),
                "interpretation": _clip(rule.get("interpretation", ""), 180),
                "trigger_clues": (rule.get("trigger_clues") or [])[:3],
            }
        )

    return items_by_dimension


def _clip(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


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


def build_analysis_prompt(
    preprocessed: dict[str, Any],
    rules: list[dict[str, Any]],
    five_dimension_index: list[dict[str, Any]],
) -> str:
    rule_context = json.dumps(
        build_five_dimension_rule_context(rules, five_dimension_index),
        ensure_ascii=False,
        indent=2,
    )
    file_context = json.dumps(preprocessed["file_summaries"], ensure_ascii=False, indent=2)
    text_context = json.dumps(preprocessed["text_snippets"], ensure_ascii=False, indent=2)

    return f"""
你是一个严谨、克制、专业的商业建筑方案 AI 诊断顾问。

你的任务是基于本地预处理结果、上传的图纸图像，以及内置商业方案五维审查规则索引，对商业建筑方案做第一轮交互式诊断。

【重要要求】
1. 当前诊断对象可能包含 PDF 拆页后的平面图、总平、立面图片或现场实拍图片。
2. 诊断必须按龙湖商业方案评价五个方面组织：大规划、大交通、大连接、大骨架、大场景。
3. 第一版不追求面面俱到，重点找出最关键、最适合在图纸上标注和讨论的问题。
4. 对能明确确认的问题，写为“错误指出”；对需要进一步量化或深化的事项，写为“复核项”或“优化建议”。
5. 每条问题都要尽量指出对应的文件、页码、楼层、区域、相对位置和建议标注方式。
6. 不要暴露底层规则编号、规则原文或规则来源明细；规则索引只作为你的内部判断依据。
7. 不要伪造尺寸、面积、页码或楼层。无法识别时写“未识别”或“需人工复核”。
8. 语气采用顾问式，不要夸奖，不要空泛。

【本地预处理结果：文件摘要】
{file_context}

【本地预处理结果：抽取到的文本片段】
{text_context}

【内置五维规则索引（内部依据，不得在输出中暴露规则编号或原文）】
{rule_context}

【输出格式】
只输出一个合法 JSON 对象，不要输出 Markdown，不要使用 ```json 代码围栏。

JSON schema：
{{
  "overall_summary": "一句话总体判断，适合总览页展示",
  "priority_dimensions": ["大交通", "大连接"],
  "dimension_reviews": [
    {{
      "dimension": "大规划",
      "risk_level": "高|中|低|待确认",
      "short_conclusion": "该维度 1-2 句话结论",
      "key_issues": [
        {{
          "issue_id": "P01",
          "issue_type": "错误指出|优化建议|复核项",
          "severity": "高|中|低",
          "issue_title": "短标题",
          "drawing_ref": {{
            "file_name": "文件名或未识别",
            "page": "页码或未识别",
            "floor": "楼层或未识别",
            "area": "空间区域或未识别",
            "relative_position": "左上|上部|右上|左中|中部|右中|左下|下部|右下|未识别",
            "annotation_type": "框选|圈选|箭头|高亮|编号点|未识别"
          }},
          "issue_description": "为什么这是问题，控制在 80 字内",
          "impact": "可能影响，控制在 60 字内",
          "recommendation": "调改建议，控制在 80 字内",
          "evidence_level": "明确可见|图面推断|需人工复核"
        }}
      ]
    }}
  ],
  "next_review_focus": ["下一轮重点复核专题 1", "下一轮重点复核专题 2"]
}}

输出约束：
- dimension_reviews 必须且只能包含：大规划、大交通、大连接、大骨架、大场景。
- 每个维度最多输出 3 个 key_issues；没有明确问题时也要给 short_conclusion，并让 key_issues 为空数组。
- issue_id 全局递增，格式 P01、P02、P03。
- 不要在输出中出现“依据规则编号”“规则来源”“规则原文”等字段。
- 不要输出总标题，不要写“项目诊断草稿”“诊断草稿”“草稿版”“Draft”等抬头。

如果某些内容证据不足，请明确写“需进一步量化/识别”，不要伪造尺寸或参数。
如果发现建标中存在明确数值、比例、净高、宽度、服务半径、广告位面积等强控指标，应作为“复核项”或“错误指出”，但仍不得暴露底层规则原文。
""".strip()


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
            text_snippets.append(f"第{page_index + 1}页：{compact_text[:500]}")

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

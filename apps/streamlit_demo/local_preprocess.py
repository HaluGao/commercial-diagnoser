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
    / "longfor_complete_rule_library_v1.json"
)


def load_rule_library() -> dict[str, Any]:
    library = json.loads(COMPLETE_RULES_PATH.read_text())
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
    return {"rules": rules, "summary": summary}


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

你的任务是基于本地预处理结果、上传的图纸图像，以及内置完整规则库，对商业建筑方案做第一轮顾问式诊断。

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

【内置完整规则库】
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

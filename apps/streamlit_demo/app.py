from __future__ import annotations

import json
import os
import re
import csv
import html
from datetime import datetime
from io import StringIO
from pathlib import Path
from uuid import uuid4

import streamlit as st

from diagnoser_provider import (
    GEMINI_NATIVE,
    OPENAI_COMPATIBLE,
    ApiYiProvider,
    ProviderConfig,
)
from local_preprocess import build_analysis_prompt, load_rule_library, preprocess_inputs


st.set_page_config(
    page_title="商业咨询智能体",
    page_icon="◇",
    layout="wide",
    initial_sidebar_state="collapsed",
)


PROJECT_STORE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "projects" / "consulting_projects.json"
)

GEMINI_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash-thinking",
]

OPENAI_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash-thinking",
]

PROTOCOL_LABELS = {
    OPENAI_COMPATIBLE: "兼容通道（推荐）",
    GEMINI_NATIVE: "Gemini 原生通道",
}

PROTOCOL_EXPLANATIONS = {
    OPENAI_COMPATIBLE: "按 API易 官方手册推荐方式接入。最稳，优先使用这一项。",
    GEMINI_NATIVE: "直接走 Gemini 原生格式。适合后续高级调试或兼容性测试。",
}

FIVE_DIMENSIONS = ["大规划", "大交通", "大连接", "大骨架", "大场景"]
RISK_COLORS = {
    "高": "oklch(0.61 0.19 28)",
    "中": "oklch(0.74 0.15 74)",
    "低": "oklch(0.64 0.14 154)",
    "待确认": "oklch(0.68 0.018 248)",
}
DIMENSION_SEQUENCE = {
    "大规划": "01",
    "大交通": "02",
    "大连接": "03",
    "大骨架": "04",
    "大场景": "05",
}




def ensure_project_store() -> None:
    PROJECT_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PROJECT_STORE_PATH.exists():
        now = datetime.now().isoformat(timespec="seconds")
        default_project = {
            "project_id": "default-project",
            "project_name": "默认咨询项目",
            "created_at": now,
            "updated_at": now,
            "records": [],
        }
        PROJECT_STORE_PATH.write_text(
            json.dumps({"projects": [default_project]}, ensure_ascii=False, indent=2) + "\n"
        )


def load_projects() -> list[dict]:
    ensure_project_store()
    payload = json.loads(PROJECT_STORE_PATH.read_text())
    return payload.get("projects", [])


def save_projects(projects: list[dict]) -> None:
    PROJECT_STORE_PATH.write_text(
        json.dumps({"projects": projects}, ensure_ascii=False, indent=2) + "\n"
    )


def get_project_by_id(projects: list[dict], project_id: str) -> dict | None:
    for project in projects:
        if project["project_id"] == project_id:
            return project
    return None


def create_project(projects: list[dict], project_name: str) -> tuple[list[dict], str]:
    new_project_id = f"project-{uuid4().hex[:8]}"
    now = datetime.now().isoformat(timespec="seconds")
    projects.insert(
        0,
        {
            "project_id": new_project_id,
            "project_name": project_name,
            "created_at": now,
            "updated_at": now,
            "records": [],
        },
    )
    save_projects(projects)
    return projects, new_project_id


def add_project_record(
    projects: list[dict],
    project_id: str,
    *,
    file_names: list[str],
    model: str,
    protocol: str,
    rule_library_version: str,
    report_content: str,
    structured_result: dict | None = None,
) -> list[dict]:
    project = get_project_by_id(projects, project_id)
    if not project:
        return projects

    now = datetime.now().isoformat(timespec="seconds")
    project["updated_at"] = now
    record = {
        "record_id": f"record-{uuid4().hex[:8]}",
        "created_at": now,
        "file_names": file_names,
        "model": model,
        "protocol": protocol,
        "rule_library_version": rule_library_version,
        "report_content": report_content,
        "report_preview": report_content[:160],
    }
    if structured_result:
        record["structured_result"] = structured_result
    project.setdefault("records", []).insert(
        0,
        record,
    )
    save_projects(projects)
    return projects


def sanitize_report_content(report: str) -> str:
    cleaned = report.strip()
    cleaned = re.sub(r"^\s*#\s*项目诊断草稿\s*\n+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*#\s*诊断草稿\s*\n+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*项目诊断草稿\s*\n+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*诊断草稿\s*\n+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def parse_structured_diagnosis(raw_text: str) -> dict | None:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None

    reviews = payload.get("dimension_reviews")
    if not isinstance(reviews, list):
        return None
    existing = {item.get("dimension") for item in reviews if isinstance(item, dict)}
    for dimension in FIVE_DIMENSIONS:
        if dimension not in existing:
            reviews.append(
                {
                    "dimension": dimension,
                    "risk_level": "待确认",
                    "short_conclusion": "本轮未形成明确结论，建议结合原图人工复核。",
                    "key_issues": [],
                }
            )
    payload["dimension_reviews"] = sorted(
        [item for item in reviews if isinstance(item, dict)],
        key=lambda item: FIVE_DIMENSIONS.index(item.get("dimension"))
        if item.get("dimension") in FIVE_DIMENSIONS
        else 99,
    )[:5]
    payload.setdefault("priority_dimensions", [])
    payload.setdefault("next_review_focus", [])
    payload.setdefault("overall_summary", "本轮已完成五维初步诊断，建议结合图纸继续复核。")
    return payload


def structured_diagnosis_to_markdown(result: dict) -> str:
    lines = [
        "## 总体判断",
        "",
        str(result.get("overall_summary", "")).strip(),
        "",
        "## 五维诊断总览",
        "",
    ]
    for review in result.get("dimension_reviews", []):
        dimension = review.get("dimension", "未分类")
        risk = review.get("risk_level", "待确认")
        conclusion = review.get("short_conclusion", "")
        lines.extend([f"### {dimension}｜{risk}风险", "", str(conclusion).strip(), ""])
        issues = review.get("key_issues") or []
        if not issues:
            lines.extend(["- 本轮未识别出明确问题。", ""])
            continue
        for issue in issues:
            ref = issue.get("drawing_ref") or {}
            lines.extend(
                [
                    f"- **{issue.get('issue_id', '')} {issue.get('issue_title', '')}**",
                    f"  - 类型：{issue.get('issue_type', '')}；严重程度：{issue.get('severity', '')}；证据等级：{issue.get('evidence_level', '')}",
                    f"  - 位置：{ref.get('file_name', '未识别')} / {ref.get('page', '未识别')} / {ref.get('floor', '未识别')} / {ref.get('area', '未识别')}",
                    f"  - 说明：{issue.get('issue_description', '')}",
                    f"  - 影响：{issue.get('impact', '')}",
                    f"  - 调改建议：{issue.get('recommendation', '')}",
                ]
            )
        lines.append("")

    focus = result.get("next_review_focus") or []
    if focus:
        lines.extend(["## 下一轮重点复核", ""])
        for item in focus:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def structured_diagnosis_to_csv(result: dict) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "问题编号",
            "五维分类",
            "问题类型",
            "严重程度",
            "文件",
            "页码",
            "楼层",
            "区域",
            "相对位置",
            "标注方式",
            "问题标题",
            "问题说明",
            "影响判断",
            "调改建议",
            "证据等级",
        ]
    )
    for review in result.get("dimension_reviews", []):
        dimension = review.get("dimension", "")
        for issue in review.get("key_issues") or []:
            ref = issue.get("drawing_ref") or {}
            writer.writerow(
                [
                    issue.get("issue_id", ""),
                    dimension,
                    issue.get("issue_type", ""),
                    issue.get("severity", ""),
                    ref.get("file_name", ""),
                    ref.get("page", ""),
                    ref.get("floor", ""),
                    ref.get("area", ""),
                    ref.get("relative_position", ""),
                    ref.get("annotation_type", ""),
                    issue.get("issue_title", ""),
                    issue.get("issue_description", ""),
                    issue.get("impact", ""),
                    issue.get("recommendation", ""),
                    issue.get("evidence_level", ""),
                ]
            )
    return output.getvalue()


def format_project_option(project: dict) -> str:
    return f"{project['project_name']} · {len(project.get('records', []))} 条"


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: oklch(0.985 0.008 238);
            --bg-soft: oklch(0.955 0.012 238);
            --ink: oklch(0.16 0.012 248);
            --muted: oklch(0.46 0.02 248);
            --faint: oklch(0.68 0.018 248);
            --line: oklch(0.84 0.014 248);
            --line-strong: oklch(0.68 0.025 248);
            --paper: oklch(0.995 0.005 238);
            --paper-ink: oklch(0.15 0.012 248);
            --accent: oklch(0.54 0.19 255);
            --accent-soft: oklch(0.91 0.045 255);
            --accent-warm: oklch(0.7 0.15 72);
            --danger: oklch(0.61 0.19 28);
            --good: oklch(0.64 0.14 154);
        }
        .stApp {
            --primary-color: var(--accent);
            --primary-color-background: var(--accent-soft);
            --primary-color-text: var(--paper);
            background:
                linear-gradient(oklch(0.88 0.01 248 / 0.45) 1px, transparent 1px),
                linear-gradient(90deg, oklch(0.88 0.01 248 / 0.4) 1px, transparent 1px),
                radial-gradient(circle at 82% 10%, oklch(0.93 0.06 255 / 0.86), transparent 30rem),
                linear-gradient(180deg, var(--paper) 0%, var(--bg) 58%, oklch(0.96 0.01 238) 100%);
            background-size: 42px 42px, 42px 42px, auto, auto;
            color: var(--ink);
        }
        header[data-testid="stHeader"] {
            background: oklch(0.985 0.008 238 / 0.9);
            backdrop-filter: blur(18px);
        }
        [data-testid="stSidebar"] {
            background: oklch(0.975 0.008 238);
            border-right: 1px solid var(--line);
        }
        [data-testid="stSidebar"] * {
            color: var(--ink);
        }
        .block-container {
            max-width: 1380px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }
        .eyebrow {
            color: var(--accent);
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        .topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            margin-bottom: 1.8rem;
            color: var(--muted);
            font-size: 0.72rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            font-weight: 800;
        }
        .topbar-rule {
            height: 1px;
            flex: 1;
            background: var(--line);
        }
        .launch-shell {
            min-height: calc(100vh - 8rem);
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(360px, 460px);
            gap: clamp(2rem, 5vw, 5.5rem);
            align-items: center;
        }
        .launch-copy {
            padding: 1.8rem 0 2.4rem 0;
        }
        .launch-kicker {
            color: var(--accent);
            font-size: 0.78rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            font-weight: 900;
            margin-bottom: 1.4rem;
        }
        .launch-title {
            color: var(--ink);
            font-size: clamp(4.2rem, 10vw, 9.8rem);
            line-height: 0.92;
            font-weight: 900;
            letter-spacing: 0;
            max-width: 980px;
            margin-bottom: 1.8rem;
        }
        .launch-lead {
            color: var(--muted);
            font-size: 1.08rem;
            line-height: 1.82;
            max-width: 720px;
        }
        .launch-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0;
            margin-top: 2.1rem;
            border-top: 1px solid var(--ink);
            border-bottom: 1px solid var(--line-strong);
            max-width: 820px;
        }
        .meta-chip {
            border-right: 1px solid var(--line);
            padding: 0.95rem 1.15rem 0.95rem 0;
            margin-right: 1.15rem;
            color: var(--ink);
            font-size: 0.78rem;
            font-weight: 800;
            white-space: nowrap;
        }
        .meta-chip:last-child {
            border-right: none;
            margin-right: 0;
        }
        .launch-panel {
            background: transparent;
            border-top: 1px solid var(--ink);
            border-bottom: 1px solid var(--line-strong);
            border-radius: 0;
            padding: 1.2rem 0 1.35rem 0;
            box-shadow: none;
        }
        .launch-panel-title {
            color: var(--ink);
            font-size: 1.22rem;
            font-weight: 900;
            margin: 0 0 0.45rem 0;
        }
        .launch-panel-copy {
            color: var(--muted);
            font-size: 0.84rem;
            line-height: 1.7;
            margin-bottom: 0;
        }
        .launch-slate {
            border-top: 1px solid var(--line-strong);
            border-bottom: 1px solid var(--line-strong);
            border-radius: 0;
            padding: 0;
            margin-top: 1.35rem;
            background: transparent;
        }
        .slate-row {
            display: grid;
            grid-template-columns: 64px 1fr;
            gap: 0.9rem;
            align-items: center;
            padding: 0.75rem 0;
            border-bottom: 1px solid var(--line);
        }
        .slate-row:last-child {
            border-bottom: none;
        }
        .slate-num {
            color: var(--accent);
            font-size: 0.74rem;
            font-weight: 900;
            letter-spacing: 0.12em;
        }
        .slate-text {
            color: var(--paper-ink);
            font-size: 0.84rem;
            line-height: 1.5;
        }
        .result-hero {
            min-height: 72vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            border-bottom: 1px solid var(--line);
            padding: 4rem 0 5.2rem 0;
        }
        .result-kicker {
            color: var(--accent);
            font-size: 0.78rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            font-weight: 900;
            margin-bottom: 1.25rem;
        }
        .result-title {
            color: var(--ink);
            font-size: clamp(2.6rem, 5.2vw, 5.25rem);
            line-height: 1.02;
            font-weight: 900;
            letter-spacing: 0;
            max-width: 980px;
            margin-bottom: 1.6rem;
        }
        .result-summary {
            color: var(--muted);
            font-size: 1.04rem;
            line-height: 1.82;
            max-width: 860px;
        }
        .scroll-cue {
            color: var(--faint);
            font-size: 0.76rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            font-weight: 900;
            margin-top: 2.6rem;
        }
        .result-section {
            padding: 4.2rem 0;
            border-bottom: 1px solid var(--line);
        }
        .section-label {
            color: var(--accent);
            font-size: 0.72rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            font-weight: 900;
            margin-bottom: 0.85rem;
        }
        .section-title {
            color: var(--ink);
            font-size: clamp(1.7rem, 3vw, 2.65rem);
            line-height: 1.15;
            font-weight: 900;
            margin-bottom: 1.1rem;
        }
        .section-copy {
            color: var(--muted);
            font-size: 0.98rem;
            line-height: 1.76;
            max-width: 760px;
        }
        .panel {
            background: var(--paper);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 1.1rem;
            margin-bottom: 1rem;
        }
        .panel-title {
            color: var(--ink);
            font-size: 1.05rem;
            font-weight: 800;
            margin-bottom: 0.35rem;
        }
        .panel-muted {
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.65;
        }
        .project-card {
            background: var(--bg-soft);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 14px;
            margin-bottom: 12px;
        }
        .project-card-title {
            color: var(--ink);
            font-size: 0.98rem;
            font-weight: 700;
            line-height: 1.45;
        }
        .project-card-meta {
            color: var(--muted);
            font-size: 0.82rem;
            margin-top: 6px;
        }
        .project-card-preview {
            color: var(--muted);
            font-size: 0.84rem;
            line-height: 1.6;
            margin-top: 8px;
        }
        .output-shell {
            background: var(--paper);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 18px;
        }
        .progress-shell {
            background: var(--paper);
            border: 1px solid var(--line-strong);
            border-radius: 14px;
            padding: 0.95rem 1rem 1rem 1rem;
            margin: 1rem 0;
        }
        .progress-row {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 1rem;
            margin-bottom: 0.6rem;
        }
        .progress-label {
            color: var(--ink);
            font-size: 0.92rem;
            font-weight: 800;
        }
        .progress-hint {
            color: var(--muted);
            font-size: 0.82rem;
            white-space: nowrap;
        }
        .upload-panel {
            padding-top: 16px;
            padding-bottom: 18px;
        }
        .summary-panel {
            min-height: 255px;
        }
        .report-panel {
            min-height: 520px;
        }
        .summary-text {
            color: var(--paper-ink);
            font-size: 0.95rem;
            line-height: 1.8;
            white-space: pre-wrap;
        }
        .fixed-viewer {
            background: var(--paper);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 14px 16px;
            overflow-y: auto;
            overflow-x: hidden;
        }
        .summary-viewer {
            height: 170px;
        }
        .report-viewer {
            height: 430px;
        }
        .viewer-empty {
            color: var(--muted);
            font-size: 0.92rem;
            line-height: 1.7;
        }
        .download-note {
            color: var(--muted);
            font-size: 0.8rem;
            margin-top: 0.35rem;
        }
        .dimension-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
            gap: 1px;
            margin: 1.4rem 0 0 0;
            border: 1px solid var(--line);
            background: var(--line);
        }
        .dimension-card {
            background: var(--paper);
            border: none;
            border-radius: 0;
            padding: 1rem;
            min-height: 150px;
        }
        .dimension-index {
            color: var(--accent);
            font-size: 0.68rem;
            font-weight: 900;
            letter-spacing: 0.12em;
            margin-bottom: 5px;
        }
        .dimension-name {
            color: var(--ink);
            font-weight: 800;
            font-size: 1rem;
            margin-bottom: 7px;
        }
        .risk-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 0.72rem;
            font-weight: 800;
            color: var(--paper);
            margin-bottom: 8px;
        }
        .dimension-summary {
            color: var(--muted);
            font-size: 0.78rem;
            line-height: 1.55;
        }
        .issue-card {
            background: var(--paper);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.85rem;
        }
        .issue-title {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 800;
            line-height: 1.45;
            margin-bottom: 7px;
        }
        .issue-meta {
            color: var(--faint);
            font-size: 0.76rem;
            line-height: 1.55;
            margin-bottom: 7px;
        }
        .issue-body {
            color: var(--paper-ink);
            font-size: 0.82rem;
            line-height: 1.65;
        }
        .dimension-detail {
            padding: 2rem 0 2.4rem 0;
            border-bottom: 1px solid var(--line);
        }
        .dimension-detail-head {
            display: grid;
            grid-template-columns: minmax(120px, 180px) minmax(0, 1fr);
            gap: 1.4rem;
            align-items: start;
            margin-bottom: 1.1rem;
        }
        .dimension-detail-index {
            color: var(--accent);
            font-size: 0.72rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            font-weight: 900;
        }
        .dimension-detail-title {
            color: var(--ink);
            font-size: 1.45rem;
            line-height: 1.2;
            font-weight: 900;
            margin-bottom: 0.45rem;
        }
        .dimension-detail-copy {
            color: var(--muted);
            font-size: 0.88rem;
            line-height: 1.7;
        }
        .dimension-empty {
            color: var(--muted);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 1rem;
            background: var(--paper);
            font-size: 0.86rem;
        }
        .download-panel {
            border: 1px solid var(--line);
            background: var(--paper);
            border-radius: 14px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .fallback-report {
            border: 1px solid var(--line);
            background: var(--paper);
            border-radius: 14px;
            padding: 1.2rem;
            color: var(--paper-ink);
            line-height: 1.8;
        }
        .stProgress > div > div > div > div {
            background: var(--accent);
        }
        .stProgress {
            margin-bottom: 0.35rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 1rem;
        }
        .stTabs [data-baseweb="tab"] {
            color: var(--muted);
        }
        .stTabs [aria-selected="true"] {
            color: var(--accent) !important;
        }
        div[data-testid="stRadio"] {
            margin: 0.8rem 0 0.8rem 0;
        }
        div[data-testid="stRadio"] [role="radiogroup"] {
            border-bottom: 1px solid var(--line-strong);
            display: flex;
            gap: 1.5rem;
            padding: 0 0 0.8rem 0;
        }
        div[data-testid="stRadio"] label,
        div[data-testid="stRadio"] p {
            color: var(--ink) !important;
            font-weight: 800 !important;
        }
        div[data-testid="stRadio"] [data-baseweb="radio"] div {
            border-color: var(--line-strong) !important;
        }
        div[data-testid="stRadio"] [data-baseweb="radio"] div[aria-checked="true"],
        div[data-testid="stRadio"] [role="radio"][aria-checked="true"] {
            border-color: var(--accent) !important;
            background-color: var(--accent) !important;
        }
        div[data-testid="stFileUploaderDropzone"] {
            background: transparent !important;
            border: 1px solid var(--line-strong) !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            padding-top: 0.9rem !important;
            padding-bottom: 0.9rem !important;
            min-height: 86px !important;
        }
        div[data-testid="stFileUploaderDropzone"] * {
            color: var(--ink) !important;
        }
        div[data-testid="stFileUploaderDropzone"] button {
            background: transparent !important;
            border: 1px solid var(--line-strong) !important;
            border-radius: 0 !important;
            color: var(--ink) !important;
            box-shadow: none !important;
        }
        input[type="radio"],
        input[type="checkbox"] {
            accent-color: var(--accent);
        }
        div.stButton > button[kind="primary"] {
            background: var(--accent) !important;
            color: var(--paper) !important;
            border: none !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            font-weight: 900 !important;
            min-height: 3.2rem !important;
        }
        div.stButton > button {
            border-radius: 0 !important;
            border-color: var(--line) !important;
            box-shadow: none !important;
        }
        div[data-testid="stDownloadButton"] button {
            border-radius: 0 !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.4rem;
        }
        .stTabs [data-baseweb="tab"] {
            color: var(--muted);
            border-radius: 12px;
        }
        .stTabs [aria-selected="true"] {
            color: var(--ink) !important;
            background: var(--accent-soft);
        }
        .plain-md {
            color: var(--paper-ink);
            line-height: 1.8;
        }
        @media (max-width: 900px) {
            .launch-shell {
                grid-template-columns: 1fr;
            }
            .dimension-detail-head {
                grid-template-columns: 1fr;
                gap: 0.5rem;
            }
            .launch-shell {
                min-height: auto;
            }
            .launch-title {
                font-size: 3.15rem;
            }
            .meta-chip {
                border-right: none;
                padding-right: 0;
                margin-right: 1rem;
            }
            .dimension-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    if "projects_loaded" not in st.session_state:
        st.session_state.projects = load_projects()
        st.session_state.active_project_id = st.session_state.projects[0]["project_id"]
        st.session_state.projects_loaded = True
    if "report_content" not in st.session_state:
        st.session_state.report_content = ""
    if "diagnosis_result" not in st.session_state:
        st.session_state.diagnosis_result = None
    if "raw_model_output" not in st.session_state:
        st.session_state.raw_model_output = ""
    if "preprocess_result" not in st.session_state:
        st.session_state.preprocess_result = None
    if "analysis_progress" not in st.session_state:
        st.session_state.analysis_progress = {"value": 0, "label": "等待开始"}
    if "api_key_ready" not in st.session_state:
        st.session_state.api_key_ready = False
    if "flash_message" not in st.session_state:
        st.session_state.flash_message = ""


def render_api_sidebar() -> tuple:
    with st.sidebar:
        st.markdown("## API 配置")
        st.caption("这个侧栏可以通过左上角箭头收起，主界面将保留项目栏和审查区。")

        provider_name = st.selectbox("服务通道", ["apiyi"], index=0)
        configured_protocol = os.environ.get("COMMERCIAL_DIAGNOSER_DEFAULT_PROTOCOL", OPENAI_COMPATIBLE).strip()
        protocol_options = [GEMINI_NATIVE, OPENAI_COMPATIBLE]
        protocol_index = protocol_options.index(configured_protocol) if configured_protocol in protocol_options else 1
        provider_protocol = st.selectbox(
            "接入方式",
            protocol_options,
            index=protocol_index,
            format_func=lambda value: PROTOCOL_LABELS[value],
        )
        st.caption(PROTOCOL_EXPLANATIONS[provider_protocol])

        configured_base_url = os.environ.get("COMMERCIAL_DIAGNOSER_BASE_URL", "").strip()
        if configured_base_url:
            default_base_url = configured_base_url
        elif provider_protocol == OPENAI_COMPATIBLE:
            default_base_url = "https://api.apiyi.com/v1"
        else:
            default_base_url = "https://api.apiyi.com"

        model_options = GEMINI_MODELS if provider_protocol == GEMINI_NATIVE else OPENAI_MODELS
        configured_model = os.environ.get("COMMERCIAL_DIAGNOSER_DEFAULT_MODEL", "").strip()
        model_index = model_options.index(configured_model) if configured_model in model_options else 0
        selected_model = st.selectbox("审查模型", model_options, index=model_index)
        base_url = st.text_input("接口地址", value=default_base_url)
        configured_api_key = os.environ.get("COMMERCIAL_DIAGNOSER_API_KEY", "").strip()
        if configured_api_key:
            api_key = configured_api_key
            st.markdown("**云端服务密钥**")
            st.info("当前演示环境已配置服务端 API Key。为避免泄露，公开页面不展示真实密钥。")
        else:
            api_key = st.text_input(
                "API Key",
                value="",
                type="password",
            )
        timeout_seconds = st.number_input("请求超时（秒）", min_value=30, max_value=600, value=240)

        provider = ApiYiProvider(
            ProviderConfig(
                provider_name=provider_name,
                protocol=provider_protocol,
                base_url=base_url,
                api_key=api_key,
                model=selected_model,
                timeout_seconds=int(timeout_seconds),
            )
        )

        st.markdown("---")
        st.markdown("### 诊断底座")
        rule_library = load_rule_library()
        foundation_rules = rule_library["rules"]
        five_dimension_index = rule_library["five_dimension_index"]
        rule_summary = rule_library["summary"]
        st.success("商业方案五维评价框架已加载")
        st.caption(f"版本 {rule_summary['version']} | 内部规则 harness 已就绪")

        st.markdown("---")
        if api_key:
            with st.spinner("验证通道中..."):
                validation = provider.validate()
            if validation.ok:
                st.success(f"{validation.indicator} {validation.summary}")
                st.session_state.api_key_ready = True
            else:
                if validation.indicator.startswith("🟡"):
                    st.warning(f"{validation.indicator} 当前配置暂不可用")
                else:
                    st.error(f"{validation.indicator} 接口暂不可用")
                st.caption(validation.summary)
                st.session_state.api_key_ready = False
            if validation.diagnostics:
                with st.expander("查看连接诊断", expanded=False):
                    st.json(validation.diagnostics)
        else:
            st.info("填入 API Key 后，这里会自动验证通道状态。")
            st.session_state.api_key_ready = False

    return (
        provider,
        selected_model,
        provider_protocol,
        rule_summary.get("library_id", "longfor-complete-rule-library-v2"),
        foundation_rules,
        five_dimension_index,
    )


def render_progress() -> tuple:
    shell = st.container()
    with shell:
        st.markdown(
            """
            <div class="progress-shell">
                <div class="progress-row">
                    <div class="progress-label">审查进度</div>
                </div>
            """,
            unsafe_allow_html=True,
        )
        progress_bar = st.progress(st.session_state.analysis_progress["value"])
        status_text = st.empty()
        status_text.caption(st.session_state.analysis_progress["label"])
        st.markdown("</div>", unsafe_allow_html=True)
    return progress_bar, status_text


def update_progress(progress_bar, status_text, value: int, label: str) -> None:
    st.session_state.analysis_progress = {"value": value, "label": label}
    progress_bar.progress(value)
    status_text.caption(label)


def render_project_rail(active_project: dict) -> None:
    projects = st.session_state.projects
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">Projects</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">新建项目栏</div>', unsafe_allow_html=True)
    st.caption("用于保存不同审查方案的咨询意见记录。")

    selected_project_id = st.selectbox(
        "当前项目",
        [project["project_id"] for project in projects],
        index=next(
            (
                idx
                for idx, project in enumerate(projects)
                if project["project_id"] == st.session_state.active_project_id
            ),
            0,
        ),
        format_func=lambda project_id: format_project_option(
            get_project_by_id(projects, project_id) or projects[0]
        ),
    )
    st.session_state.active_project_id = selected_project_id

    new_project_name = st.text_input("新建项目名称", placeholder="例如：惠山TOD-首轮咨询")
    if st.button("新建项目", use_container_width=True) and new_project_name.strip():
        updated_projects, new_id = create_project(projects, new_project_name.strip())
        st.session_state.projects = updated_projects
        st.session_state.active_project_id = new_id
        st.rerun()

    current_project = get_project_by_id(st.session_state.projects, st.session_state.active_project_id) or active_project
    st.caption(
        f"创建于 {current_project['created_at']} · 最近更新 {current_project['updated_at']}"
    )
    st.markdown("---")
    st.markdown('<div class="panel-title">咨询记录</div>', unsafe_allow_html=True)
    if current_project.get("records"):
        for record in current_project["records"][:10]:
            file_names = "、".join(record.get("file_names", [])[:2]) or "未命名文件"
            st.markdown(
                f"""
                <div class="project-card">
                    <div class="project-card-title">{file_names}</div>
                    <div class="project-card-meta">{record['created_at']} · {record['model']} · {record['protocol']}</div>
                    <div class="project-card-preview">{record['report_preview']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("这个项目还没有咨询记录。跑完一次审查后，会自动保存在这里。")
    st.markdown("</div>", unsafe_allow_html=True)


def render_dimension_overview(result: dict) -> None:
    overall = html.escape(str(result.get("overall_summary", "本轮已完成五维初步诊断。")))
    st.markdown(
        f"""
        <div class="section-copy">{overall}</div>
        """,
        unsafe_allow_html=True,
    )

    cards: list[str] = ['<div class="dimension-grid">']
    reviews = {item.get("dimension"): item for item in result.get("dimension_reviews", [])}
    for dimension in FIVE_DIMENSIONS:
        review = reviews.get(dimension, {})
        risk = str(review.get("risk_level", "待确认"))
        color = RISK_COLORS.get(risk, RISK_COLORS["待确认"])
        conclusion = html.escape(str(review.get("short_conclusion", "本轮未形成明确结论。")))
        issue_count = len(review.get("key_issues") or [])
        cards.append(
            f"""
                <div class="dimension-card">
                    <div class="dimension-index">{DIMENSION_SEQUENCE.get(dimension, "00")} / FIVE-DIMENSION REVIEW</div>
                    <div class="dimension-name">{dimension}</div>
                <div class="risk-pill" style="background:{color};">{risk}风险 · {issue_count}项</div>
                <div class="dimension-summary">{conclusion}</div>
            </div>
            """
        )
    cards.append("</div>")
    st.markdown("".join(cards), unsafe_allow_html=True)


def render_issue_card(dimension: str, issue: dict) -> None:
    ref = issue.get("drawing_ref") or {}
    severity = str(issue.get("severity", "待确认"))
    issue_type = str(issue.get("issue_type", "复核项"))
    title = html.escape(f"{issue.get('issue_id', '')} {issue.get('issue_title', '')}".strip())
    meta = html.escape(
        f"{dimension} · {issue_type} · {severity} · "
        f"{ref.get('file_name', '未识别')} / {ref.get('page', '未识别')} / "
        f"{ref.get('floor', '未识别')} / {ref.get('area', '未识别')} / "
        f"{ref.get('relative_position', '未识别')} / {ref.get('annotation_type', '未识别')}"
    )
    body = html.escape(
        f"问题：{issue.get('issue_description', '')}\n"
        f"影响：{issue.get('impact', '')}\n"
        f"建议：{issue.get('recommendation', '')}\n"
        f"证据：{issue.get('evidence_level', '')}"
    ).replace("\n", "<br>")
    color = RISK_COLORS.get(severity, RISK_COLORS["待确认"])
    st.markdown(
        f"""
        <div class="issue-card" style="border-color:{color};">
            <div class="issue-title">{title}</div>
            <div class="issue-meta">{meta}</div>
            <div class="issue-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dimension_details(result: dict) -> None:
    reviews = {item.get("dimension"): item for item in result.get("dimension_reviews", [])}
    for dimension in FIVE_DIMENSIONS:
        review = reviews.get(dimension, {})
        risk = html.escape(str(review.get("risk_level", "待确认")))
        conclusion = html.escape(str(review.get("short_conclusion", "本轮未形成明确结论。")))
        issue_count = len(review.get("key_issues") or [])
        st.markdown(
            f"""
            <section class="dimension-detail">
                <div class="dimension-detail-head">
                    <div class="dimension-detail-index">{DIMENSION_SEQUENCE.get(dimension, "00")} / {risk}风险 / {issue_count}项</div>
                    <div>
                        <div class="dimension-detail-title">{dimension}</div>
                        <div class="dimension-detail-copy">{conclusion}</div>
                    </div>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        issues = review.get("key_issues") or []
        if not issues:
            st.markdown(
                '<div class="dimension-empty">本轮未识别出明确问题，建议在下一轮结合原图纸继续人工复核。</div>',
                unsafe_allow_html=True,
            )
            continue
        for issue in issues:
            render_issue_card(dimension, issue)


def render_downloads(result: dict, report_content: str) -> None:
    st.markdown(
        """
        <div class="download-panel">
            <div class="panel-title">导出成果</div>
            <div class="panel-muted">交互页面用于阅读和讨论，文件导出用于留痕、转发和后续整理。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "问题清单 CSV",
            data=structured_diagnosis_to_csv(result),
            file_name="commercial_consulting_issues.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_b:
        st.download_button(
            "附加报告 Markdown",
            data=report_content,
            file_name="commercial_consulting_report.md",
            mime="text/markdown",
            use_container_width=True,
        )


def render_upload_controls() -> tuple:
    input_mode = st.radio(
        "输入方式",
        ["上传文件", "现场拍照"],
        horizontal=True,
        label_visibility="collapsed",
    )
    uploaded_files = None
    camera_photo = None
    if input_mode == "上传文件":
        uploaded_files = st.file_uploader(
            "上传 PDF / 图片",
            type=["pdf", "png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
    else:
        camera_photo = st.camera_input("现场拍照输入", label_visibility="collapsed")
    run_analysis = st.button("开始五维审查", type="primary", use_container_width=True)
    return uploaded_files, camera_photo, run_analysis


def render_launch_page() -> tuple:
    if st.session_state.flash_message:
        st.toast(st.session_state.flash_message, icon="✅")
        st.session_state.flash_message = ""

    st.markdown(
        """
        <div class="topbar">
            <div>商业咨询智能体</div>
            <div class="topbar-rule"></div>
            <div>五维方案审查</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left_col, right_col = st.columns([1.08, 0.62], gap="large")
    with left_col:
        st.markdown(
            """
            <div class="launch-copy">
                <div class="launch-kicker">Plan Review / Consulting Workbench</div>
                <div class="launch-title">商业咨询<br>智能体</div>
                <div class="launch-lead">
                    面向商业建筑方案的五维智能审查工作台。上传 PDF、平面图或现场外拍后，系统按大规划、大交通、
                    大连接、大骨架、大场景展开判断，输出关键问题、影响判断和调改建议。
                </div>
                <div class="launch-meta">
                    <div class="meta-chip">大规划</div>
                    <div class="meta-chip">大交通</div>
                    <div class="meta-chip">大连接</div>
                    <div class="meta-chip">大骨架</div>
                    <div class="meta-chip">大场景</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right_col:
        st.markdown(
            """
            <div class="launch-panel">
                <div class="launch-panel-title">启动一次方案审查</div>
                <div class="launch-panel-copy">先放入材料，再进入结果页。分析前页面保持干净，不预演结论。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        uploaded_files, camera_photo, run_analysis = render_upload_controls()
        st.markdown(
            """
            <div class="launch-slate">
                <div class="slate-row">
                    <div class="slate-num">01</div>
                    <div class="slate-text">识别图纸、页码、文本片段和可用于多模态分析的图像。</div>
                </div>
                <div class="slate-row">
                    <div class="slate-num">02</div>
                    <div class="slate-text">调用内部五维 harness，形成问题优先级和复核路径。</div>
                </div>
                <div class="slate-row">
                    <div class="slate-num">03</div>
                    <div class="slate-text">输出总体判断、关键问题、影响和调改建议。</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        progress_bar = st.empty()
        status_text = st.empty()
    if st.session_state.preprocess_result:
        with st.expander("查看本地预处理结果", expanded=False):
            st.json(st.session_state.preprocess_result["file_summaries"])
            if st.session_state.preprocess_result["text_snippets"]:
                st.markdown("**抽取文本片段**")
                for snippet in st.session_state.preprocess_result["text_snippets"][:10]:
                    st.write(f"- {snippet}")
            st.write(
                f"进入线上多模态分析的图像数量：{len(st.session_state.preprocess_result['media_items'])}"
            )

    return uploaded_files, camera_photo, run_analysis, progress_bar, status_text


def render_results_page() -> tuple:
    result = st.session_state.diagnosis_result
    report = st.session_state.report_content

    st.markdown(
        """
        <div class="topbar">
            <div>审查结果</div>
            <div class="topbar-rule"></div>
            <div>向下查看问题</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if result:
        summary = html.escape(str(result.get("overall_summary", "本轮已完成五维初步诊断。")))
        st.markdown(
            f"""
            <section class="result-hero">
                <div class="result-kicker">Five-Dimension Diagnosis</div>
                <div class="result-title">审查完成。先看结论，再看问题。</div>
                <div class="result-summary">{summary}</div>
                <div class="scroll-cue">向下滚动查看五维诊断</div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <section class="result-section">
                <div class="section-label">Overview</div>
                <div class="section-title">五维风险总览</div>
                <div class="section-copy">先判断问题落在哪些维度，再决定下一轮复核顺序。</div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        render_dimension_overview(result)
        st.markdown(
            """
            <section class="result-section">
                <div class="section-label">Findings</div>
                <div class="section-title">关键问题与调改建议</div>
                <div class="section-copy">每条问题都尽量包含位置、严重程度、影响和建议。下一步产品化会把这些问题映射到原图纸标注上。</div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        render_dimension_details(result)
        st.markdown(
            """
            <section class="result-section">
                <div class="section-label">Export</div>
                <div class="section-title">导出与留痕</div>
                <div class="section-copy">页面交互是主成果，Markdown 和 CSV 用于会议纪要、转发和后续整理。</div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        render_downloads(result, report)
        with st.expander("查看附加文字报告", expanded=False):
            st.markdown(report)
        with st.expander("查看结构化诊断 JSON", expanded=False):
            st.json(result)
    else:
        st.markdown(
            f"""
            <section class="result-hero">
                <div class="result-kicker">Text Report</div>
                <div class="result-title">审查完成，当前结果为文字报告。</div>
                <div class="result-summary">模型未返回完整结构化 JSON，本轮先展示附加咨询报告。</div>
            </section>
            <div class="fallback-report">{html.escape(report).replace(chr(10), "<br>")}</div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("重新上传并启动新的审查", expanded=False):
        uploaded_files, camera_photo, run_analysis = render_upload_controls()
        progress_bar = st.empty()
        status_text = st.empty()
    return uploaded_files, camera_photo, run_analysis, progress_bar, status_text


inject_styles()
init_state()
(
    provider,
    selected_model,
    provider_protocol,
    rule_library_version,
    foundation_rules,
    five_dimension_index,
) = render_api_sidebar()
active_project = get_project_by_id(
    st.session_state.projects, st.session_state.active_project_id
) or st.session_state.projects[0]
has_result = bool(st.session_state.diagnosis_result or st.session_state.report_content)
if has_result:
    uploaded_files, camera_photo, run_analysis, progress_bar, status_text = render_results_page()
else:
    uploaded_files, camera_photo, run_analysis, progress_bar, status_text = render_launch_page()

if run_analysis:
    if not st.session_state.api_key_ready:
        st.error("请先在系统配置侧栏完成服务配置，并确认通道可用。")
        update_progress(progress_bar, status_text, 0, "等待 API 配置完成")
    elif not uploaded_files and not camera_photo:
        st.error("请先上传 PDF / 图片，或拍照输入。")
        update_progress(progress_bar, status_text, 0, "等待上传审查材料")
    else:
        try:
            update_progress(progress_bar, status_text, 12, "整理方案材料")
            preprocessed = preprocess_inputs(uploaded_files, camera_photo)
            st.session_state.preprocess_result = preprocessed

            update_progress(progress_bar, status_text, 34, "构建五维审查上下文")
            prompt = build_analysis_prompt(preprocessed, foundation_rules, five_dimension_index)

            update_progress(progress_bar, status_text, 62, "执行多模态五维审查")
            raw_output = provider.generate_report(
                prompt=prompt,
                media_items=preprocessed["media_items"],
            )
            st.session_state.raw_model_output = raw_output
            structured_result = parse_structured_diagnosis(raw_output)
            if structured_result:
                report = structured_diagnosis_to_markdown(structured_result)
            else:
                report = sanitize_report_content(raw_output)

            update_progress(progress_bar, status_text, 84, "生成问题卡片与附加报告")
            st.session_state.report_content = report
            st.session_state.diagnosis_result = structured_result
            file_names: list[str] = []
            if uploaded_files:
                file_names.extend([item.name for item in uploaded_files])
            if camera_photo:
                file_names.append(camera_photo.name or "camera_capture.jpg")
            st.session_state.projects = add_project_record(
                st.session_state.projects,
                st.session_state.active_project_id,
                file_names=file_names,
                model=selected_model,
                protocol=provider_protocol,
                rule_library_version=rule_library_version,
                report_content=report,
                structured_result=structured_result,
            )

            update_progress(progress_bar, status_text, 100, "完成")
            st.session_state.flash_message = "审查完成，咨询意见已保存。"
            st.rerun()
        except Exception as exc:
            update_progress(progress_bar, status_text, 0, "审查中断")
            st.error(f"审查失败：{exc}")

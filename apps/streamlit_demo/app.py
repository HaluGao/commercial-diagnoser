from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import streamlit as st

from diagnoser_provider import (
    GEMINI_NATIVE,
    OPENAI_COMPATIBLE,
    ApiYiProvider,
    ProviderConfig,
)
from local_preprocess import (
    FORMAL_ONLY,
    IMPORTED_ONLY,
    MERGED_ALL,
    build_analysis_prompt,
    load_rule_library,
    preprocess_inputs,
)


st.set_page_config(
    page_title="商业咨询智能体",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
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

RULE_MODE_LABELS = {
    MERGED_ALL: "合并模式（正式28 + 复核底库569）",
    FORMAL_ONLY: "正式基础规则库（28条）",
    IMPORTED_ONLY: "复核底库（569条）",
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
    rule_mode: str,
    report_content: str,
) -> list[dict]:
    project = get_project_by_id(projects, project_id)
    if not project:
        return projects

    now = datetime.now().isoformat(timespec="seconds")
    project["updated_at"] = now
    project.setdefault("records", []).insert(
        0,
        {
            "record_id": f"record-{uuid4().hex[:8]}",
            "created_at": now,
            "file_names": file_names,
            "model": model,
            "protocol": protocol,
            "rule_mode": rule_mode,
            "report_content": report_content,
            "report_preview": report_content[:160],
        },
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


def format_project_option(project: dict) -> str:
    return f"{project['project_name']} · {len(project.get('records', []))} 条"


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #05070d;
            color: #f3f5f7;
        }
        header[data-testid="stHeader"] {
            background: rgba(5, 7, 13, 0.92);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0b1020 0%, #0a0f19 100%);
            border-right: 1px solid rgba(255,255,255,0.06);
        }
        [data-testid="stSidebar"] * {
            color: #edf2f7;
        }
        .block-container {
            max-width: 1420px;
            padding-top: 3.8rem;
            padding-bottom: 2rem;
        }
        .main-shell {
            background: #05070d;
        }
        .panel {
            background: linear-gradient(180deg, rgba(16,19,31,0.98) 0%, rgba(11,14,24,0.98) 100%);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 22px;
            padding: 20px;
            box-shadow: 0 18px 48px rgba(0,0,0,0.34);
            margin-bottom: 1rem;
        }
        .hero-panel {
            background: linear-gradient(135deg, rgba(13,17,27,0.98) 0%, rgba(17,22,34,0.98) 100%);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 26px;
            padding: 22px 24px 18px 24px;
            margin-bottom: 0.8rem;
            box-shadow: 0 20px 56px rgba(0,0,0,0.38);
            min-height: 190px;
            overflow: hidden;
        }
        .eyebrow {
            color: #8e9ab2;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        .hero-title {
            color: #f8fafc;
            font-size: 3rem;
            line-height: 1.03;
            letter-spacing: -0.04em;
            font-weight: 800;
            margin-bottom: 0.5rem;
        }
        .hero-subtitle {
            color: #a7b0c0;
            font-size: 0.96rem;
            line-height: 1.65;
            max-width: 620px;
        }
        .panel-title {
            color: #f8fafc;
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }
        .panel-muted {
            color: #94a3b8;
            font-size: 0.9rem;
            line-height: 1.65;
        }
        .project-card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            padding: 14px;
            margin-bottom: 12px;
        }
        .project-card-title {
            color: #ffffff;
            font-size: 0.98rem;
            font-weight: 700;
            line-height: 1.45;
        }
        .project-card-meta {
            color: #8ea0bc;
            font-size: 0.82rem;
            margin-top: 6px;
        }
        .project-card-preview {
            color: #c9d3e3;
            font-size: 0.84rem;
            line-height: 1.6;
            margin-top: 8px;
        }
        .output-shell {
            background: rgba(255,255,255,0.025);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 18px;
            padding: 18px;
        }
        .progress-shell {
            background: rgba(255,255,255,0.025);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 18px;
            padding: 12px 16px 14px 16px;
            margin-bottom: 0.9rem;
        }
        .progress-row {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 1rem;
            margin-bottom: 0.6rem;
        }
        .progress-label {
            color: #edf2f7;
            font-size: 0.92rem;
            font-weight: 700;
        }
        .progress-hint {
            color: #8ea0bc;
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
            color: #d7deea;
            font-size: 0.95rem;
            line-height: 1.8;
            white-space: pre-wrap;
        }
        .fixed-viewer {
            background: rgba(255,255,255,0.025);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 18px;
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
            color: #8ea0bc;
            font-size: 0.92rem;
            line-height: 1.7;
        }
        .download-note {
            color: #8ea0bc;
            font-size: 0.8rem;
            margin-top: 0.35rem;
        }
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #ff5a5f 0%, #ff8661 100%);
        }
        .stProgress {
            margin-bottom: 0.35rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 1rem;
        }
        .stTabs [data-baseweb="tab"] {
            color: #b6c0d0;
        }
        .stTabs [aria-selected="true"] {
            color: #ffffff !important;
        }
        div[data-testid="stFileUploaderDropzone"] {
            background: rgba(255,255,255,0.03) !important;
            border: 1px dashed rgba(255,255,255,0.16) !important;
            border-radius: 18px !important;
            padding-top: 0.8rem !important;
            padding-bottom: 0.8rem !important;
        }
        div.stButton > button[kind="primary"] {
            background: linear-gradient(90deg, #ff4d57 0%, #ff6847 100%) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 16px !important;
            font-weight: 700 !important;
            min-height: 3.2rem !important;
        }
        div.stButton > button {
            border-radius: 14px !important;
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
        st.markdown("### 规则范围")
        rule_mode = st.selectbox(
            "规则加载模式",
            [MERGED_ALL, FORMAL_ONLY, IMPORTED_ONLY],
            index=0,
            format_func=lambda value: RULE_MODE_LABELS[value],
        )
        rule_library = load_rule_library(rule_mode)
        foundation_rules = rule_library["rules"]
        rule_summary = rule_library["summary"]
        st.success(f"当前加载规则 {rule_summary['selected_rule_count']} 条")
        st.caption(
            f"正式库 {rule_summary['formal_rule_count']} 条 | 复核底库 {rule_summary['imported_candidate_count']} 条"
        )

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

    return provider, selected_model, provider_protocol, rule_mode, foundation_rules


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


inject_styles()
init_state()
provider, selected_model, provider_protocol, rule_mode, foundation_rules = render_api_sidebar()
active_project = get_project_by_id(
    st.session_state.projects, st.session_state.active_project_id
) or st.session_state.projects[0]
main_col, right_col = st.columns([1.32, 1], gap="large")

with main_col:
    if st.session_state.flash_message:
        st.toast(st.session_state.flash_message, icon="✅")
        st.session_state.flash_message = ""

    st.markdown(
        """
        <div class="hero-panel">
            <div class="eyebrow">Commercial Consulting Agent</div>
            <div class="hero-title">商业咨询智能体</div>
            <div class="hero-subtitle">
                智能多模态商业方案审查平台。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    progress_bar, status_text = render_progress()

    st.markdown('<div class="eyebrow">Input</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">上传审查材料</div>', unsafe_allow_html=True)
    st.caption("上传方案 PDF 或图片后即可开始审查。")
    upload_tab, camera_tab = st.tabs(["设计图纸", "手机外拍"])
    with upload_tab:
        uploaded_files = st.file_uploader(
            "上传 PDF / 图片",
            type=["pdf", "png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
    with camera_tab:
        camera_photo = st.camera_input("现场拍照输入", label_visibility="collapsed")

    run_analysis = st.button("开始审查", type="primary", use_container_width=True)

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

with right_col:
    st.markdown('<div class="panel-title">摘要</div>', unsafe_allow_html=True)
    if st.session_state.report_content:
        summary_text = st.session_state.report_content[:420]
        if len(st.session_state.report_content) > 420:
            summary_text += "..."
        st.markdown(
            f'<div class="fixed-viewer summary-viewer"><div class="summary-text">{summary_text}</div></div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "摘要下载",
            data=summary_text,
            file_name="commercial_consulting_summary.md",
            mime="text/markdown",
            use_container_width=True,
        )
    else:
        st.markdown(
            '<div class="viewer-empty" style="margin-bottom:0.8rem;">完成一次审查后，这里会显示摘要内容。</div>',
            unsafe_allow_html=True,
        )
        st.button("摘要下载", disabled=True, use_container_width=True)

    st.markdown('<div class="panel-title">完整咨询报告</div>', unsafe_allow_html=True)
    if st.session_state.report_content:
        report_view = (
            st.session_state.report_content
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        st.markdown(
            f'<div class="fixed-viewer report-viewer"><div class="summary-text">{report_view}</div></div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "咨询报告下载",
            data=st.session_state.report_content,
            file_name="commercial_consulting_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
    else:
        st.markdown(
            '<div class="viewer-empty" style="margin-bottom:0.8rem;">完整报告会在审查完成后显示在这里。</div>',
            unsafe_allow_html=True,
        )
        st.button("咨询报告下载", disabled=True, use_container_width=True)

if run_analysis:
    if not st.session_state.api_key_ready:
        st.error("请先在左侧 API 配置页完成配置，并确认通道可用。")
        update_progress(progress_bar, status_text, 0, "等待 API 配置完成")
    elif not uploaded_files and not camera_photo:
        st.error("请先上传 PDF / 图片，或拍照输入。")
        update_progress(progress_bar, status_text, 0, "等待上传审查材料")
    else:
        try:
            update_progress(progress_bar, status_text, 12, "🏃 整理材料")
            preprocessed = preprocess_inputs(uploaded_files, camera_photo)
            st.session_state.preprocess_result = preprocessed

            update_progress(progress_bar, status_text, 34, "🏃 抽取上下文")
            prompt = build_analysis_prompt(preprocessed, foundation_rules)

            update_progress(progress_bar, status_text, 62, "🏃 多模态审查")
            report = provider.generate_report(
                prompt=prompt,
                media_items=preprocessed["media_items"],
            )
            report = sanitize_report_content(report)

            update_progress(progress_bar, status_text, 84, "🏃 写入记录")
            st.session_state.report_content = report
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
                rule_mode=rule_mode,
                report_content=report,
            )

            update_progress(progress_bar, status_text, 100, "完成")
            st.session_state.flash_message = "审查完成，咨询意见已保存。"
            st.rerun()
        except Exception as exc:
            update_progress(progress_bar, status_text, 0, "审查中断")
            st.error(f"审查失败：{exc}")

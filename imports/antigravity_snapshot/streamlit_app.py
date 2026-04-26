import streamlit as st
import json
import os
import time
import base64
import requests
import fitz
from tenacity import retry, wait_exponential, stop_after_attempt
from loguru import logger

# Page config
st.set_page_config(page_title="商业建筑方案AI诊断器", page_icon="🏗️", layout="wide")

# ==========================================
# 🌌 Stitch Vibe UI Injection (Deep Dark, Aurora, Glass Box)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
        color: #FFFFFF !important;
    }

    /* Animated Aurora Background (Stitch Style) */
    @keyframes gradientBG {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    .stApp {
        background-color: #05050A !important;
        background-image: 
            radial-gradient(ellipse at 80% 100%, rgba(138, 43, 226, 0.25) 0%, transparent 50%),
            radial-gradient(ellipse at 20% 80%, rgba(59, 130, 246, 0.2) 0%, transparent 50%),
            url("data:image/svg+xml,%3Csvg width='20' height='20' viewBox='0 0 20 20' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%23ffffff' fill-opacity='0.03' fill-rule='evenodd'%3E%3Ccircle cx='3' cy='3' r='1'/%3E%3C/g%3E%3C/svg%3E");
        background-attachment: fixed;
    }

    /* Hide default header */
    header {visibility: hidden;}

    /* Sidebar Styling (Deep blending) */
    [data-testid="stSidebar"] {
        background: rgba(5, 5, 10, 0.6) !important;
        backdrop-filter: blur(20px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    [data-testid="stSidebar"] * {
        color: #E2E8F0 !important;
    }

    /* The Massive Stitch-Like Input Box */
    /* Target the Tabs container which will act as our Box */
    div[data-testid="stTabs"] {
        background: rgba(25, 20, 35, 0.5) !important;
        backdrop-filter: blur(40px) saturate(150%) !important;
        -webkit-backdrop-filter: blur(40px) saturate(150%) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 24px !important;
        padding: 1.5rem !important;
        box-shadow: 0 30px 60px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05) !important;
        margin-top: 2rem !important;
        margin-bottom: 2rem !important;
    }

    /* Tab Switchers (Pills) */
    div[data-testid="stTabs"] button {
        background-color: rgba(255, 255, 255, 0.03) !important;
        border-radius: 30px !important;
        border: 1px solid transparent !important;
        padding: 0.3rem 1.2rem !important;
        margin-right: 0.5rem !important;
        color: #94A3B8 !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2) !important;
    }

    /* Uploader Area (Transparent inside Box) */
    [data-testid="stFileUploaderDropzone"] {
        background-color: transparent !important;
        border: 1px dashed rgba(255, 255, 255, 0.2) !important;
        border-radius: 12px !important;
        padding: 2rem !important;
        transition: all 0.3s ease;
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: #A855F7 !important;
        background: rgba(168, 85, 247, 0.05) !important;
    }
    
    /* Uploaded File Item Box */
    [data-testid="stUploadedFile"] {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border-radius: 8px !important;
    }

    /* Primary Start Button (Glowing Aura Edge) */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #8B5CF6 0%, #3B82F6 100%) !important;
        color: #FFFFFF !important;
        border-radius: 30px !important;
        border: none !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        box-shadow: 0 0 20px rgba(139, 92, 246, 0.4) !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
    }
    div.stButton > button[kind="primary"]:hover {
        box-shadow: 0 0 35px rgba(139, 92, 246, 0.6) !important;
        transform: translateY(-2px);
    }
    div.stButton > button[kind="primary"]:disabled {
        background: rgba(255,255,255,0.1) !important;
        box-shadow: none !important;
        color: rgba(255,255,255,0.3) !important;
    }

    /* Secondary Clear Button */
    div.stButton > button[kind="secondary"] {
        background-color: transparent !important;
        color: #94A3B8 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 30px !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: rgba(255, 255, 255, 0.05) !important;
        color: #FFFFFF !important;
    }

    /* Report Section Containers */
    .stMarkdown {
        color: #E2E8F0 !important;
    }
    
    /* Make Title Text Transparent Gradient */
    .hero-title {
        text-align: center;
        font-size: 4.5rem;
        font-weight: 700;
        letter-spacing: -0.04em;
        margin-top: 2rem;
        margin-bottom: 0.5rem;
        background: linear-gradient(180deg, #FFFFFF 0%, #A1A1AA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-subtitle {
        text-align: center;
        font-size: 1.25rem;
        color: #94A3B8;
        font-weight: 400;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# API keys will be resolved dynamically from UI

@st.cache_data(show_spinner=False, ttl=60)
def validate_model_access(model_name, test_key, base_url):
    if not test_key: return False, "未配置 API Key"
    try:
        # Strip trailing slash from base url just in case
        base_url = base_url.rstrip('/')
        endpoint = f"{base_url}/v1beta/models/{model_name}:generateContent?key={test_key}"
        payload = {"contents": [{"role": "user", "parts": [{"text": "1"}]}], "generationConfig": {"maxOutputTokens": 1}}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {test_key}"
        }
            
        res = requests.post(endpoint, json=payload, headers=headers, timeout=5)
        if res.status_code == 200:
            return True, "🟢"
        else:
            return False, f"🔴 [{res.status_code}]"
    except Exception as e:
        return False, "🔴 连接失败"


if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'report_content' not in st.session_state:
    st.session_state.report_content = ""

# Sidebar for Knowledge Base stats
st.sidebar.header("📚 知识库状态")
rules_path = "extracted_rules.json"

if os.path.exists(rules_path):
    with open(rules_path, "r", encoding="utf-8") as f:
        rules = json.load(f)
    st.sidebar.success(f"已加载内置规范: {len(rules)} 条")
    
    with st.sidebar.expander("查看当前规范抽样"):
        st.json(rules[:3] if len(rules) >= 3 else rules)
else:
    st.sidebar.warning("尚未提取出结构化规范数据库 (extracted_rules.json)。请先运行后台提取脚本。")
    rules = []

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ 引擎设置 (原生专属通道)")

# 强制降维打击：锁定 1.5-flash 为绝对首选，避开 Pro 级的配额封锁
selected_model = st.sidebar.selectbox(
    "解析模型", 
    ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-pro"], 
    index=0
)
default_key = os.environ.get("GEMINI_API_KEY", "")
api_key = st.sidebar.text_input("GEMINI API Key", value=default_key, type="password", help="在此填入您的 API Key")
base_url = st.sidebar.text_input("API 代理地址", value="https://api.apiyi.com", help="如果您使用中转服务（如 AIP易），请输入对应的接口地址")

# --- 添加连通性状态指示灯 ---
if api_key and selected_model:
    with st.sidebar:
        with st.spinner("正在验证原生通道..."):
            is_valid, indicator_msg = validate_model_access(selected_model, api_key, base_url)
            if is_valid:
                st.success(f"**{indicator_msg} 通道顺畅！该模型就绪。**")
            else:
                st.error(f"**{indicator_msg}，密钥已耗尽或无效！**")

# Centered Landing Page Hero
st.markdown('<div class="hero-title">Design at the speed of AI</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">Transform Floorplans into Pro Diagnostic Reports.</div>', unsafe_allow_html=True)

# Main centered column to mimic the Stitch Box width
col_spacer1, col_main, col_spacer2 = st.columns([1, 4, 1])

with col_main:
    # 顶部清理工具 (小巧的次级按钮)
    col_clear, _ = st.columns([1, 5])
    with col_clear:
        if st.button("🧹 重新开始", use_container_width=True):
            st.session_state.uploader_key += 1
            st.session_state.report_content = ""
            st.rerun()

    # == The Stitch Box Replica ==
    tab1, tab2 = st.tabs(["[ ]  上传设计图纸", "[ ]  手机外拍实景"])
    
    with tab1:
        uploaded_files = st.file_uploader(
            "我们要审阅什么样的方案图面？", 
            type=["png", "jpg", "jpeg", "pdf"], 
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.uploader_key}"
        )
        if uploaded_files:
            for file in uploaded_files:
                if file.type.startswith('image'):
                    st.image(file, caption=f"已挂载: {file.name}", use_container_width=True)
                elif file.type == 'application/pdf':
                    st.info(f"📄 已挂载 PDF 母卷: {file.name}")
                    
    with tab2:
        st.markdown("<p style='font-size:0.9em;color:#94A3B8; text-align:center;'>使用手机浏览器访问该网页，唤起镜头拍摄现场导视牌 / 空间图：</p>", unsafe_allow_html=True)
        camera_photo = st.camera_input("拍照输入", key=f"camera_{st.session_state.uploader_key}")

    has_files = bool(uploaded_files) or bool(camera_photo)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("✨ 立即生成专属 AI 分析", type="primary", disabled=not has_files):
        if not api_key:
            st.error("环境缺失 API_KEY！请在终端 export GEMINI_API_KEY 或 AITOLL_API_KEY 后重新启动应用。")
        elif not rules:
            st.error("规范库为空，请先完善规则库。")
        else:
            with st.spinner("AI 正在交叉比对图纸参数与内置规范..."):
                try:
                    # 将扁平的规则库进行框架性/章节性梳理
                    CHAPTER_MAPPING = {
                        "一、商业动线与客流交通": ["动线", "交通", "客流", "电梯", "扶梯", "接驳", "道路", "到达", "视线"],
                        "二、空间尺度与面积标准": ["层高", "空间", "高程", "面积", "尺寸", "尺度", "高差"],
                        "三、核心业态与铺位落位": ["铺", "租客", "超市", "影院", "业态", "主力店", "多经点", "落位", "商管"],
                        "四、立面景观与设备消防": ["立面", "设备", "消防", "结构", "采光", "景观", "展面", "界面", "屋顶"],
                        "五、商业价值与运营策略": ["成本", "指标", "财务", "价值", "运营", "目标", "策略", "评估", "经济"]
                    }
                    
                    def assign_chapter(category):
                        for chapter, keywords in CHAPTER_MAPPING.items():
                            if any(kw in category for kw in keywords):
                                return chapter
                        return "六、通用设计与综合规范"
                        
                    structured_rules = {}
                    for r in rules:
                        cat = r.get("category", "")
                        chapter_name = assign_chapter(cat)
                        if chapter_name not in structured_rules:
                            structured_rules[chapter_name] = {}
                        if cat not in structured_rules[chapter_name]:
                            structured_rules[chapter_name][cat] = []
                        structured_rules[chapter_name][cat].append(r)

                    rules_context = json.dumps(structured_rules, ensure_ascii=False)
                    
                    prompt = f"""
                    你是一个严谨、客观的商业建筑设计审核系统。
                    请审查本次上传的这组图纸或方案说明文件 (包含平立剖面图或PDF文本)。
                    
                    以下是我们的【内部审核规则库】：
                    {rules_context}
                    
                    你的任务和输出要求：
                    1. 直接切入正题，【不需要】在开篇总结项目内容，也【不需要】夸奖方案做得好的地方。达到规则要求是设计的底线。
                    2. 评估规则适用性：不要生搬硬套。只评估图面中实际存在的内容与相应规则的符合度。
                    3. 输出语调：客观、精确、平实、中立。无需过于激烈或带有情绪化指责。
                    4. 定位问题要求：在描述问题时，必须基于文件内的文字、图纸标题或楼层标识来定位，例如“在三层平面图中...”、“在酒店大堂剖面图中...”。【绝对禁止】使用“图1、图2”这种流水号描述，因为图序毫无意义。
                    5. 输出格式：直接输出一份清晰、正规的体系化 Markdown 审核诊断报告。核心必须包括以下要求：
                       - 👉 **必须严格以规则库的【6大框架性章节】作为诊断报告的主体大标题**（如：一、商业动线与客流交通...等）。
                       - 👉 在每个大标题内，如果审查出相应专业的图纸存在问题，分为以下板块输出：
                         🚨 【合规性驳回】：客观列举违反了本章内部规则的具体事实。（要求：位置定位明确；实际图面参数是多少；标准参数是多少；冲突何在）。
                         💡 【优化性建议】：虽然未触犯硬性指标，但在本框架（如流线布局、空间感受等）下可以更巧妙的主观改善建议。
                       - 👉 如果某个一级框架章节下，上传图纸表现完美、或者图纸内容不包含该章节的审查要素，必须简短列出该大标题并在下方标注“✅ 本章节图纸涵盖内容评估合规，无异常。”（确保所有章节标题完整展现，维护报告的体系感）。
                    """
                    
                    # 统一图像预处理 (整合文件列表与摄像头捕获)
                    b64_images = []
                    
                    if uploaded_files:
                        for file in uploaded_files:
                            if file.type == 'application/pdf':
                                pdf_bytes = file.read()
                                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                                for page_num in range(len(doc)):
                                    page = doc.load_page(page_num)
                                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                                    img_bytes = pix.tobytes("jpeg")
                                    b64_images.append(base64.b64encode(img_bytes).decode('utf-8'))
                            else:
                                b64_images.append(base64.b64encode(file.read()).decode('utf-8'))
                                
                    if camera_photo:
                        b64_images.append(base64.b64encode(camera_photo.read()).decode('utf-8'))

                    # 构建原生负载结构
                    b_url = base_url.rstrip('/')
                    endpoint = f"{b_url}/v1beta/models/{selected_model}:generateContent?key={api_key}"
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}"
                    }
                    
                    parts = [{"text": prompt}]
                    for b64 in b64_images:
                        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
                        
                    payload = {
                        "contents": [{"role": "user", "parts": parts}],
                        "generationConfig": {"temperature": 0.1}
                    }
                    
                    def generate_with_retry():
                        status_placeholder = st.empty()
                        for attempt in range(8):  # 最高允许重试 8 次以应对并发限流
                            try:
                                res = requests.post(endpoint, headers=headers, json=payload, timeout=240)
                                if res.status_code == 200:
                                    status_placeholder.empty()
                                    return res.json()["candidates"][0]["content"]["parts"][0]["text"]
                                    
                                elif res.status_code == 429:
                                    # 自动拦截 429 Quota Exceeded 前端等待
                                    wait_time = 40 + (attempt * 10)
                                    status_placeholder.warning(f"⚠️ 触发 Google 免费额度限流保护 (15 RPM)。全自动冷却休眠 {wait_time} 秒后将无缝重试...")
                                    time.sleep(wait_time)
                                    continue
                                    
                                elif res.status_code >= 500:
                                    # 针对503拥堵进行自动指数退避重试
                                    time.sleep(2 ** attempt + 3)
                                    continue
                                else:
                                    # 400级别的错误（如：Payload Too Large、Key无效），立刻中止抛出原始信息！
                                    raise Exception(f"Google 引擎拒绝了请求 (HTTP {res.status_code}): {res.text}")
                            except requests.exceptions.RequestException as e:
                                if attempt == 7:
                                    raise Exception(f"网络连接失败: {e}")
                                time.sleep(2 ** attempt + 3)
                                
                        raise Exception("官方服务器响应超时或受制于超长红线配额，请稍后重试。")
                        
                    st.session_state.report_content = generate_with_retry()
                        
                except Exception as e:
                    st.error(f"诊断过程出错: {e}")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.session_state.report_content:
        st.markdown("### 📋 深度 AI 联合诊断报告")
        st.markdown(st.session_state.report_content)
        st.download_button(
            label="⬇️ 导出 Markdown 报告",
            data=st.session_state.report_content,
            file_name="Stitch_Vision_Report.md",
            mime="text/markdown"
        )

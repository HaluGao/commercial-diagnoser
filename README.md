# 商业咨询智能体 / 商业建筑方案 AI 诊断器

面向商业建筑方案评审场景的多模态 Agent Demo。

本项目聚焦购物中心及复合商业前期方案审看，支持上传平面图、PDF、效果图或拍照材料，通过“本地预处理 + 多模态推理 + 规则 harness 约束”的方式，生成顾问式咨询摘要和完整诊断报告。

## Demo Value

这个演示版重点验证三件事：

- 输入商业建筑方案图纸或图片后，能够完成第一轮读图诊断
- 输出结果不是普通问答，而是结构化、顾问式的咨询意见
- 诊断不是模型自由发挥，而是建立在商业前期规则 harness 之上

## Core Moat: Harness

本产品最重要的不是接了多模态模型，而是构建了一套面向商业建筑方案审查的 `harness`。

这套 harness 的本质，是把龙湖商业大前期能力中可复用、可判断、可解释的审查经验，沉淀为结构化底层规则。当前已形成 **569 条底层规则**，它们共同定义了：

- 方案诊断的判断标准
- 输出意见的依据来源
- 顾问式结论的表达边界
- 规则持续扩充与复核的演进框架

这意味着，本产品的结果并不是通用模型的自由生成，而是建立在龙湖商业前期真实能力、真实标准和真实项目经验上的“有依据诊断”。

这也是当前 Demo 最大的壁垒：

- 外部产品可以做图纸识别，但拿不到这套判断标准
- 外部模型可以给表层建议，但做不到基于龙湖大前期能力的体系化判断
- 没有这套 harness，就很难形成稳定、可复核、可持续扩展的商业方案咨询能力

## Current Capabilities

- 多模态输入：支持 PDF、PNG、JPG、JPEG、WebP
- 顾问式输出：同时给出摘要与完整咨询报告
- 规则库驱动：支持正式规则库、复核底库和合并模式
- 网页工作台：支持上传、查看结果、下载 Markdown
- 可持续扩展：规则库、样本、脚本和 schema 已具备继续扩充基础

## Repository Layout

```text
commercial_diagnoser/
├── apps/streamlit_demo/      # 当前网页 Demo
├── data/                     # 规则库、项目记录、样本与处理中间产物
├── examples/                 # JSON 样例
├── imports/                  # 导入快照与中间材料
├── schemas/                  # 核心数据结构
├── scripts/                  # 数据处理与规则抽取脚本
├── submission/               # 比赛提交材料工作区
├── requirements.txt          # 演示版最小依赖
├── streamlit_app.py          # 托管平台入口
└── DEPLOY_DEMO.md            # 演示版部署说明
```

## Local Run

推荐使用独立 Python 环境运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

本地启动后默认访问：

- `http://localhost:8501`

如果需要指定端口：

```bash
streamlit run streamlit_app.py --server.port 8515
```

## Environment Variables

演示版建议支持以下环境变量：

- `COMMERCIAL_DIAGNOSER_API_KEY`
- `COMMERCIAL_DIAGNOSER_BASE_URL`
- `COMMERCIAL_DIAGNOSER_DEFAULT_PROTOCOL`
- `COMMERCIAL_DIAGNOSER_DEFAULT_MODEL`

推荐演示值：

- `COMMERCIAL_DIAGNOSER_BASE_URL=https://api.apiyi.com/v1`
- `COMMERCIAL_DIAGNOSER_DEFAULT_PROTOCOL=openai_compatible`
- `COMMERCIAL_DIAGNOSER_DEFAULT_MODEL=gemini-2.5-pro`

## Fastest Hosted Demo Path

当前最快的公网演示路径：

1. 将本目录单独放入 GitHub 仓库
2. 连接到 Streamlit Community Cloud
3. Main file path 选择 `streamlit_app.py`
4. 在平台环境变量中填入上面的 API 配置
5. 发布演示链接

更详细的说明见：

- [DEPLOY_DEMO.md](./DEPLOY_DEMO.md)

## Notes

- 当前版本适合作为演示型公网 Demo
- 若长期面向中国大陆用户稳定使用，后续建议迁移到中国大陆云服务器
- 当前重点是“演示链路可跑通”，不是最终生产级架构

# 演示版部署说明

## 推荐路径

优先将 `commercial_diagnoser/` 单独作为 GitHub 仓库，再部署到 Streamlit Community Cloud。

## 最小部署文件

- `requirements.txt`
- `streamlit_app.py`
- `apps/streamlit_demo/`
- `data/rules/`
- `data/projects/consulting_projects.json`

## 建议环境变量

- `COMMERCIAL_DIAGNOSER_API_KEY`
- `COMMERCIAL_DIAGNOSER_BASE_URL=https://api.apiyi.com/v1`
- `COMMERCIAL_DIAGNOSER_DEFAULT_PROTOCOL=openai_compatible`
- `COMMERCIAL_DIAGNOSER_DEFAULT_MODEL=gemini-2.5-pro`

## Streamlit Community Cloud

- Main file path: `streamlit_app.py`
- Python dependencies: 自动读取 `requirements.txt`

## 说明

当前版本更适合作为演示型公网 Demo。若面向中国大陆长期稳定使用，后续建议迁移到中国大陆云服务器。

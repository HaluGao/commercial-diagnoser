# Streamlit Demo

该目录是 codex 项目内的原生 demo。

特点：

- 使用 codex 当前正式基础规则库
- 采用 `本地预处理 + API易外部推理`
- 支持 `gemini_native` 与 `openai_compatible` 两种协议模式
- 默认按 API易 文档优先使用 `openai_compatible`
- 调用 Gemini 时，优先建议在 OpenAI 兼容模式下直接填写 Gemini 模型名，例如 `gemini-2.5-flash`

启动示例：

```bash
/Users/halu/Desktop/Antigravity/venv/bin/streamlit run /Users/halu/Desktop/codex/commercial_diagnoser/apps/streamlit_demo/app.py --server.port 8511 --server.headless true
```

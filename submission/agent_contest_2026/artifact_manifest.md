# 封装包建议目录

建议最终提交包结构如下：

```text
黑马大赛+团队名称+商业咨询智能体.zip
├── README.md
├── data_desensitization_declaration.md
├── demo_video.mp4
├── demo_materials/
│   ├── sample_input/
│   ├── sample_output/
│   └── screenshots/
├── source_package/
│   └── commercial_diagnoser/
└── deploy_guide/
    └── quick_start.md
```

## 当前项目内可复用资产

- Web Demo
  - `/Users/halu/Desktop/codex/commercial_diagnoser/apps/streamlit_demo/app.py`
- 规则库
  - `/Users/halu/Desktop/codex/commercial_diagnoser/data/rules/longfor/longfor_foundation_rules_all.json`
  - `/Users/halu/Desktop/codex/commercial_diagnoser/data/rules/review/antigravity/antigravity_review_base_library.json`
- 样本诊断结果
  - `/Users/halu/Desktop/codex/commercial_diagnoser/data/source_ingest/huishan_tod_0409/diagnosis_report.framework_draft.v1.md`

## 后续待补

- 演示截图
- 输入/输出样例包
- 启动说明精简版
- 视频脚本定稿

#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render a diagnosis report JSON file into Markdown."
    )
    parser.add_argument("--input", required=True, help="Path to diagnosis report JSON.")
    parser.add_argument("--output", required=True, help="Path to output Markdown file.")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text())


def render_item(item):
    lines = [f"### {item['title']}", ""]
    lines.append(f"- 证据类型：`{item['finding_type']}`")
    lines.append(f"- 依据归属：`{item['basis_type']}`")
    lines.append(f"- 严重度：`{item['severity']}`")
    lines.append(f"- 主题：{item['category_l1']} / {item['category_l2']}")
    lines.append(f"- 摘要：{item['summary']}")
    if item.get("detailed_analysis"):
        lines.append(f"- 说明：{item['detailed_analysis']}")
    lines.append("- 证据位置：")
    for evidence in item["evidence_refs"]:
        region = evidence["region_id"] if evidence["region_id"] else "未分区"
        lines.append(
            f"  - 第{evidence['page_index'] + 1}页 / {region} / {evidence['description']}"
        )
    lines.append(f"- 规则引用：{', '.join(item['rule_refs'])}")
    lines.append(f"- 建议：{item['recommendation']}")
    if item.get("confidence") is not None:
        lines.append(f"- 置信度：{item['confidence']:.2f}")
    lines.append("")
    return "\n".join(lines)


def main():
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = load_json(input_path)

    lines = [f"# {report['project_info']['project_name']} 诊断报告", ""]
    lines.append("## 总体判断")
    lines.append("")
    lines.append(report["executive_summary"]["overall_view"])
    lines.append("")

    if report["executive_summary"].get("key_strengths"):
        lines.append("### 主要优势")
        lines.append("")
        for item in report["executive_summary"]["key_strengths"]:
            lines.append(f"- {item}")
        lines.append("")

    if report["executive_summary"].get("key_risks"):
        lines.append("### 主要风险")
        lines.append("")
        for item in report["executive_summary"]["key_risks"]:
            lines.append(f"- {item}")
        lines.append("")

    lines.append("## 错误指出意见")
    lines.append("")
    if report["issues"]:
        for item in report["issues"]:
            lines.append(render_item(item))
    else:
        lines.append("当前版本暂无明确错误指出意见。")
        lines.append("")

    lines.append("## 优化性意见")
    lines.append("")
    if report["optimizations"]:
        for item in report["optimizations"]:
            lines.append(render_item(item))
    else:
        lines.append("当前版本暂无优化性意见。")
        lines.append("")

    if report.get("citations"):
        lines.append("## 依据索引")
        lines.append("")
        for citation in report["citations"]:
            lines.append(
                f"- `{citation['citation_id']}` {citation['source_type']} / {citation['source_file']} / {citation['source_locator']} / {citation['quoted_or_paraphrased_text']}"
            )
        lines.append("")

    output_path.write_text("\n".join(lines))
    print(json.dumps({"status": "ok", "output_path": str(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Initialize a fact pack stub from a prepared PDF document manifest."
    )
    parser.add_argument("--manifest", required=True, help="Path to document_manifest.json")
    parser.add_argument("--output", required=True, help="Path to write fact_pack.stub.json")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text())


def main():
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = load_json(manifest_path)

    pages = []
    for page in manifest["pages"]:
        text_blocks = []
        if page["text_excerpt"]:
            text_blocks.append(
                {
                    "text": page["text_excerpt"],
                    "confidence": 1.0,
                    "bbox": None,
                }
            )

        pages.append(
            {
                "page_index": page["page_index"],
                "page_label": page["page_label"],
                "text_blocks": text_blocks,
                "visual_regions": [],
            }
        )

    fact_pack = {
        "document_id": manifest["sample_id"],
        "project_name": manifest["project_name"],
        "input_files": [
            {
                "path": manifest["input_pdf_path"],
                "file_type": "pdf",
                "page_count": manifest["page_count"],
            }
        ],
        "pages": pages,
        "recognized_elements": [],
        "derived_facts": [],
        "uncertainties": [
            {
                "topic": "visual_region_detection",
                "reason": "Visual regions have not been annotated yet.",
                "recommended_followup": "Run the next-stage page region parser and element recognizer."
            }
        ],
    }

    output_path.write_text(json.dumps(fact_pack, ensure_ascii=False, indent=2))
    print(json.dumps({"status": "ok", "output_path": str(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

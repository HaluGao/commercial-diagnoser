#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Merge detailed region annotations into a fact pack JSON file."
    )
    parser.add_argument("--fact-pack", required=True, help="Path to source fact pack JSON.")
    parser.add_argument("--regions", required=True, help="Path to detailed region JSON.")
    parser.add_argument("--output", required=True, help="Path to output merged fact pack JSON.")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text())


def main():
    args = parse_args()
    fact_pack_path = Path(args.fact_pack).expanduser().resolve()
    regions_path = Path(args.regions).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fact_pack = load_json(fact_pack_path)
    region_data = load_json(regions_path)

    by_page = {}
    for region in region_data["regions"]:
        by_page.setdefault(region["page_index"], []).append(region)

    for page in fact_pack["pages"]:
        page_index = page["page_index"]
        detailed_regions = []
        for region in by_page.get(page_index, []):
            detailed_regions.append(
                {
                    "region_id": region["region_id"],
                    "region_type": "plan",
                    "summary": f"{region['label']}：{region['diagnostic_notes']}",
                    "bbox": region["bbox"],
                }
            )

        if detailed_regions:
            page["visual_regions"] = detailed_regions

    output_path.write_text(json.dumps(fact_pack, ensure_ascii=False, indent=2))
    print(json.dumps({"status": "ok", "output_path": str(output_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

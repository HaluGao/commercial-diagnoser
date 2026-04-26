#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from PIL import Image, ImageOps


def parse_args():
    parser = argparse.ArgumentParser(
        description="Crop evidence regions from prepared page preview images."
    )
    parser.add_argument("--spec", required=True, help="Path to region crop spec JSON.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where cropped evidence images will be written.",
    )
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text())


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def main():
    args = parse_args()
    spec_path = Path(args.spec).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_dir(output_dir)

    spec = load_json(spec_path)
    manifest = {
        "sample_id": spec["sample_id"],
        "generated_from": str(spec_path),
        "outputs": [],
    }

    for item in spec["regions"]:
        image_path = Path(item["image_path"])
        image = Image.open(image_path)
        x1, y1, x2, y2 = item["bbox"]
        cropped = image.crop((x1, y1, x2, y2))

        # Add a light border so cropped evidence is easier to read in reports.
        cropped = ImageOps.expand(cropped, border=8, fill="white")

        output_path = output_dir / f"{item['region_id']}.png"
        cropped.save(output_path)

        manifest["outputs"].append(
            {
                "region_id": item["region_id"],
                "page_index": item["page_index"],
                "label": item["label"],
                "output_path": str(output_path),
            }
        )

    manifest_path = output_dir / "crop_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({"status": "ok", "manifest_path": str(manifest_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

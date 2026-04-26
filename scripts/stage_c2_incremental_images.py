#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


C2_CACHE_DIR = Path(
    "/Users/halu/Desktop/codex/commercial_diagnoser/data/source_ingest/c2_incremental_cache"
)
EXISTING_NORMALIZED_PATH = Path(
    "/Users/halu/Desktop/codex/commercial_diagnoser/data/rules/imported/antigravity/antigravity_rule_candidates.normalized.json"
)
INCREMENTAL_RAW_PATH = Path(
    "/Users/halu/Desktop/codex/commercial_diagnoser/data/rules/imported/c2_incremental/c2_incremental_extracted_rules.raw.json"
)
MANIFEST_PATH = C2_CACHE_DIR / "cache_manifest.json"


def numeric_image_sort_key(path: Path) -> int:
    try:
        return int(path.stem)
    except ValueError:
        return 99999


def resolve_local_c2_dir(cli_source_dir: str | None) -> Path:
    source_dir_value = cli_source_dir or os.environ.get("COMMERCIAL_DIAGNOSER_LOCAL_C2_DIR")
    if not source_dir_value:
        raise RuntimeError(
            "未设置本地 C2 副本目录。请先把需要保留下载的图片手动放到本地目录，再通过 "
            "--source-dir 或 COMMERCIAL_DIAGNOSER_LOCAL_C2_DIR 指定该目录。"
        )

    source_dir = Path(source_dir_value).expanduser()
    if not source_dir.exists() or not source_dir.is_dir():
        raise RuntimeError(f"本地 C2 副本目录不存在或不可用：{source_dir}")
    return source_dir


def build_missing_image_list(source_dir: Path) -> list[Path]:
    existing_rules = json.loads(EXISTING_NORMALIZED_PATH.read_text())
    processed_images = {item.get("source_image") for item in existing_rules if item.get("source_image")}
    if INCREMENTAL_RAW_PATH.exists():
        incremental_rules = json.loads(INCREMENTAL_RAW_PATH.read_text())
        processed_images.update(
            {item.get("source_image") for item in incremental_rules if item.get("source_image")}
        )
    all_images = sorted(source_dir.glob("*.png"), key=numeric_image_sort_key)
    return [path for path in all_images if path.name not in processed_images]


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage remaining C2 images into a local cache directory.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--source-dir", type=str, default=None, help="Directory of the manually prepared local C2 image copies.")
    args = parser.parse_args()

    C2_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    source_dir = resolve_local_c2_dir(args.source_dir)
    missing_images = build_missing_image_list(source_dir)
    if args.limit is not None:
        missing_images = missing_images[: args.limit]

    staged: list[str] = []
    skipped: list[str] = []
    for source_path in missing_images:
        target_path = C2_CACHE_DIR / source_path.name
        if target_path.exists():
            skipped.append(source_path.name)
            continue
        print(f"Staging {source_path.name}...", flush=True)
        shutil.copy2(source_path, target_path)
        staged.append(source_path.name)

    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "cache_dir": str(C2_CACHE_DIR),
                "source_dir": str(source_dir),
                "requested_count": len(missing_images),
                "staged_count": len(staged),
                "skipped_existing_count": len(skipped),
                "staged_images": staged,
                "skipped_images": skipped,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "requested_count": len(missing_images),
                "staged_count": len(staged),
                "skipped_existing_count": len(skipped),
                "cache_manifest": str(MANIFEST_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

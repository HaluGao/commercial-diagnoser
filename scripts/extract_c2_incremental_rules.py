#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib import error, request

from PIL import Image


C2_CACHE_DIR = Path(
    "/Users/halu/Desktop/codex/commercial_diagnoser/data/source_ingest/c2_incremental_cache"
)
EXISTING_NORMALIZED_PATH = Path(
    "/Users/halu/Desktop/codex/commercial_diagnoser/data/rules/imported/antigravity/antigravity_rule_candidates.normalized.json"
)
OUTPUT_DIR = Path(
    "/Users/halu/Desktop/codex/commercial_diagnoser/data/rules/imported/c2_incremental"
)
RAW_OUTPUT_PATH = OUTPUT_DIR / "c2_incremental_extracted_rules.raw.json"
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / "c2_incremental_extracted_rules.summary.json"
MISSING_MANIFEST_PATH = OUTPUT_DIR / "c2_incremental_missing_images.json"


def numeric_image_sort_key(path: Path) -> int:
    try:
        return int(path.stem)
    except ValueError:
        return 99999


def resolve_api_key() -> str | None:
    for key_name in [
        "COMMERCIAL_DIAGNOSER_API_KEY",
        "APIYI_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
    ]:
        value = os.environ.get(key_name)
        if value:
            return value
    return None


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
    if RAW_OUTPUT_PATH.exists():
        incremental_rules = json.loads(RAW_OUTPUT_PATH.read_text())
        processed_images.update(
            {item.get("source_image") for item in incremental_rules if item.get("source_image")}
        )
    all_images = sorted(source_dir.glob("*.png"), key=numeric_image_sort_key)
    missing_images = [path for path in all_images if path.name not in processed_images]
    return missing_images


def resolve_image_path(image_name: str, source_dir: Path) -> Path:
    cached_path = C2_CACHE_DIR / image_name
    if cached_path.exists():
        return cached_path
    return source_dir / image_name


def build_prompt() -> str:
    return """
你是一个资深的商业建筑咨询顾问和规则抽取专家。

请仔细阅读这张来自【龙湖 C2工具】的图片，提取其中可以沉淀为“方案评价规则 / 设计判断依据”的内容。

要求：
1. 只提取可复用的判断依据，不要把纯封面、页码、装饰性口号当成规则。
2. 如果图片里是案例事实、项目参数或单一项目说明，也可以提取，但要保留原始对象与指标。
3. 一条独立判断依据拆成一条记录。
4. 表格按行拆分。
5. 返回必须为 JSON 数组。

返回字段：
- category
- target
- metric
- value
- rule_desc

示例：
[
  {
    "category": "商业动线",
    "target": "次要走道",
    "metric": "宽度",
    "value": ">=2.0m",
    "rule_desc": "商业次要动线走道宽度不得小于2.0米。"
  }
]

如果图片没有实质规则，请返回 []。
""".strip()


def build_request_payload(image_path: Path) -> dict[str, Any]:
    mime_type, image_b64 = prepare_image_payload(image_path)
    return {
        "model": os.environ.get("COMMERCIAL_DIAGNOSER_EXTRACTION_MODEL", "gemini-2.5-flash-thinking"),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_prompt()},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": 2500,
    }


def parse_response_json(response_json: dict[str, Any]) -> list[dict[str, Any]]:
    message = response_json["choices"][0]["message"]["content"]
    if isinstance(message, list):
        text_parts = [item.get("text", "") for item in message if isinstance(item, dict)]
        content_str = "\n".join(text_parts).strip()
    else:
        content_str = str(message).strip()

    if content_str.startswith("```json"):
        content_str = content_str[7:]
    if content_str.startswith("```"):
        content_str = content_str[3:]
    if content_str.endswith("```"):
        content_str = content_str[:-3]
    content_str = content_str.strip()

    try:
        parsed = json.loads(content_str)
    except json.JSONDecodeError:
        parsed = _extract_embedded_json(content_str)

    if isinstance(parsed, dict) and "rules" in parsed:
        parsed = parsed["rules"]
    if not isinstance(parsed, list):
        raise ValueError("模型返回的 JSON 不是数组。")
    return parsed


def _extract_embedded_json(content_str: str) -> list[dict[str, Any]] | dict[str, Any]:
    array_match = re.search(r"\[[\s\S]*\]", content_str)
    if array_match:
        return json.loads(array_match.group(0))

    object_match = re.search(r"\{[\s\S]*\}", content_str)
    if object_match:
        return json.loads(object_match.group(0))

    raise ValueError(f"未能从模型返回中提取 JSON。原始内容片段：{content_str[:500]}")


def prepare_image_payload(image_path: Path) -> tuple[str, str]:
    # Downscale and convert images into lighter JPEG payloads to reduce multimodal latency.
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / f"{image_path.stem}.jpg"
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            image.thumbnail((1600, 1600))
            image.save(output_path, format="JPEG", quality=84, optimize=True)
        image_b64 = base64.b64encode(output_path.read_bytes()).decode("utf-8")
        return "image/jpeg", image_b64


def request_rule_extraction(image_path: Path, api_key: str, base_url: str, timeout_seconds: int) -> list[dict[str, Any]]:
    payload = build_request_payload(image_path)
    req = request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            response_json = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

    parsed_rules = parse_response_json(response_json)
    for rule in parsed_rules:
        rule["source_image"] = image_path.name
    return parsed_rules


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract rules only from C2 images not yet processed before.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N missing images.")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--source-dir", type=str, default=None, help="Directory of the manually prepared local C2 image copies.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_dir = resolve_local_c2_dir(args.source_dir)
    missing_images = build_missing_image_list(source_dir)

    MISSING_MANIFEST_PATH.write_text(
        json.dumps(
            {
                "c2_dir": str(source_dir),
                "missing_image_count": len(missing_images),
                "missing_images": [path.name for path in missing_images],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    if args.limit is not None:
        missing_images = missing_images[: args.limit]

    api_key = resolve_api_key()
    if not api_key:
        raise RuntimeError(
            "未找到可用 API key。请先在 shell 中设置 COMMERCIAL_DIAGNOSER_API_KEY 或 APIYI_API_KEY。"
        )

    base_url = os.environ.get("COMMERCIAL_DIAGNOSER_BASE_URL", "https://api.apiyi.com/v1")
    extracted_rules: list[dict[str, Any]] = []
    failed_images: list[dict[str, str]] = []
    if RAW_OUTPUT_PATH.exists():
        extracted_rules = json.loads(RAW_OUTPUT_PATH.read_text())

    for image_path in missing_images:
        try:
            print(f"Processing {image_path.name}...", flush=True)
            parsed_rules = request_rule_extraction(
                image_path=resolve_image_path(image_path.name, source_dir),
                api_key=api_key,
                base_url=base_url,
                timeout_seconds=args.timeout,
            )
            extracted_rules.extend(parsed_rules)
            RAW_OUTPUT_PATH.write_text(json.dumps(extracted_rules, ensure_ascii=False, indent=2) + "\n")
            print(f"Completed {image_path.name}: {len(parsed_rules)} rules", flush=True)
            time.sleep(3)
        except Exception as exc:
            print(f"Failed {image_path.name}: {exc}", flush=True)
            failed_images.append({"image": image_path.name, "error": str(exc)})

    SUMMARY_OUTPUT_PATH.write_text(
        json.dumps(
            {
                "base_url": base_url,
                "requested_image_count": len(missing_images),
                "extracted_rule_count": len(extracted_rules),
                "failed_images": failed_images,
                "raw_output_path": str(RAW_OUTPUT_PATH),
                "missing_manifest_path": str(MISSING_MANIFEST_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    print(
        json.dumps(
            {
                "requested_image_count": len(missing_images),
                "extracted_rule_count": len(extracted_rules),
                "failed_image_count": len(failed_images),
                "raw_output_path": str(RAW_OUTPUT_PATH),
                "summary_output_path": str(SUMMARY_OUTPUT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

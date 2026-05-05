#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / 'data' / 'rules' / 'imported' / 'tianjie_standard_2024'
RAW_OUTPUT_PATH = OUTPUT_DIR / 'tianjie_standard_2024_extracted_rules.raw.json'
SUMMARY_OUTPUT_PATH = OUTPUT_DIR / 'tianjie_standard_2024_extracted_rules.summary.json'
PROCESSED_PAGES_PATH = OUTPUT_DIR / 'tianjie_standard_2024_processed_pages.json'
MISSING_MANIFEST_PATH = OUTPUT_DIR / 'tianjie_standard_2024_missing_images.json'
DEFAULT_SOURCE_DIR = Path('/Users/halu/临时工作文件/商业咨询智能体/龙湖天街建标-2024版')


def numeric_image_sort_key(path: Path) -> int:
    try:
        return int(path.stem)
    except ValueError:
        return 99999


def canonical_image_name(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix or '.png'
    if stem.isdigit():
        return f"{int(stem)}{suffix.lower()}"
    return f"{stem}{suffix.lower()}"


def resolve_api_key() -> str | None:
    for key_name in [
        'COMMERCIAL_DIAGNOSER_API_KEY',
        'APIYI_API_KEY',
        'OPENAI_API_KEY',
        'GEMINI_API_KEY',
    ]:
        value = os.environ.get(key_name)
        if value:
            return value
    return None


def load_processed_page_names() -> set[str]:
    if not PROCESSED_PAGES_PATH.exists():
        return set()
    payload = json.loads(PROCESSED_PAGES_PATH.read_text())
    return {canonical_image_name(name) for name in payload.get('processed_pages', [])}


def save_processed_page_names(names: set[str]) -> None:
    PROCESSED_PAGES_PATH.write_text(
        json.dumps({'processed_pages': sorted(names)}, ensure_ascii=False, indent=2) + '\n'
    )


def build_missing_image_list(source_dir: Path) -> list[Path]:
    processed_images = load_processed_page_names()
    if RAW_OUTPUT_PATH.exists():
        incremental_rules = json.loads(RAW_OUTPUT_PATH.read_text())
        processed_images.update(
            {
                canonical_image_name(item.get('source_image'))
                for item in incremental_rules
                if item.get('source_image')
            }
        )
    all_images = sorted(source_dir.glob('*.png'), key=numeric_image_sort_key)
    return [path for path in all_images if canonical_image_name(path.name) not in processed_images]


def build_prompt() -> str:
    return """
你是一个资深的商业建筑建造标准研究员和规则抽取专家。

请仔细阅读这张来自【龙湖天街建造标准（2024版）建筑（含立面）篇】的图片，提取其中可沉淀为“方案评价规则 / 技术控制指标 / 强控红线 / 设计判断依据”的内容。

特别要求：
1. 优先提取带有明确技术性、准确性和可判断性的规则，尤其是面积、宽度、净高、高度、深宽比、服务半径、距离、数量、比例、机房面积、广告位面积等指标。
2. 立面、广告位、标识、照明、机房、后勤、卫生间、自动扶梯、坡扶梯、客梯、货梯、交通接驳等强控要求要重点提取。
3. 如果图片包含表格，请按行拆分成多条规则。
4. 忽略封面、页码、纯章节标题。
5. 忽略红色高亮、红框、后期人工批注、单项目备注、一次性结论以及“项目一事一议”类信息。
6. 一条独立判断依据拆成一条记录。
7. 返回必须为 JSON 数组。

返回字段：
- category
- target
- metric
- value
- rule_desc

示例：
[
  {
    "category": "建造标准与安全底线",
    "target": "商业卫生间",
    "metric": "服务半径",
    "value": "<=80m",
    "rule_desc": "商业卫生间服务半径不应大于80米。"
  }
]

如果图片没有实质规则，请返回 []。
""".strip()


def prepare_image_payload(image_path: Path) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / f'{image_path.stem}.jpg'
        with Image.open(image_path) as image:
            image = image.convert('RGB')
            image.thumbnail((1800, 1800))
            image.save(output_path, format='JPEG', quality=88, optimize=True)
        image_b64 = base64.b64encode(output_path.read_bytes()).decode('utf-8')
        return 'image/jpeg', image_b64


def build_request_payload(image_path: Path) -> dict[str, Any]:
    mime_type, image_b64 = prepare_image_payload(image_path)
    return {
        'model': os.environ.get('COMMERCIAL_DIAGNOSER_EXTRACTION_MODEL', 'gemini-2.5-flash-thinking'),
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': build_prompt()},
                    {
                        'type': 'image_url',
                        'image_url': {'url': f'data:{mime_type};base64,{image_b64}'},
                    },
                ],
            }
        ],
        'temperature': 0.1,
        'max_tokens': 3200,
    }


def _extract_embedded_json(content_str: str) -> list[dict[str, Any]] | dict[str, Any]:
    decoder = json.JSONDecoder()
    for marker in ('[', '{'):
        start = content_str.find(marker)
        while start != -1:
            try:
                parsed, _ = decoder.raw_decode(content_str[start:])
                return parsed
            except json.JSONDecodeError:
                start = content_str.find(marker, start + 1)

    array_match = re.search(r'\[[\s\S]*?\]', content_str)
    if array_match:
        return json.loads(array_match.group(0))

    object_match = re.search(r'\{[\s\S]*?\}', content_str)
    if object_match:
        return json.loads(object_match.group(0))

    raise ValueError(f'未能从模型返回中提取 JSON。原始内容片段：{content_str[:500]}')


def parse_response_json(response_json: dict[str, Any]) -> list[dict[str, Any]]:
    message = response_json['choices'][0]['message']['content']
    if isinstance(message, list):
        text_parts = [item.get('text', '') for item in message if isinstance(item, dict)]
        content_str = '\n'.join(text_parts).strip()
    else:
        content_str = str(message).strip()

    if content_str.startswith('```json'):
        content_str = content_str[7:]
    if content_str.startswith('```'):
        content_str = content_str[3:]
    if content_str.endswith('```'):
        content_str = content_str[:-3]
    content_str = content_str.strip()

    if not content_str:
        raise ValueError('模型返回为空内容。')

    try:
        parsed = json.loads(content_str)
    except json.JSONDecodeError:
        parsed = _extract_embedded_json(content_str)

    if isinstance(parsed, dict):
        if 'rules' in parsed and isinstance(parsed['rules'], list):
            parsed = parsed['rules']
        elif len(parsed) == 1:
            only_value = next(iter(parsed.values()))
            if isinstance(only_value, list):
                parsed = only_value
        elif {'category', 'target', 'metric', 'value', 'rule_desc'}.issubset(parsed.keys()):
            parsed = [parsed]

    if not isinstance(parsed, list):
        raise ValueError('模型返回的 JSON 不是数组。')
    return parsed


def request_rule_extraction(image_path: Path, api_key: str, base_url: str, timeout_seconds: int) -> list[dict[str, Any]]:
    payload = build_request_payload(image_path)
    req = request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            response_json = json.loads(response.read().decode('utf-8'))
    except error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f'HTTP {exc.code}: {detail}') from exc

    parsed_rules = parse_response_json(response_json)
    for rule in parsed_rules:
        rule['source_image'] = image_path.name
    return parsed_rules


def main() -> None:
    parser = argparse.ArgumentParser(description='Extract technical rules from Longfor Tianjie 2024 standard images.')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--source-dir', type=str, default=str(DEFAULT_SOURCE_DIR))
    parser.add_argument('--only-images', type=str, default=None)
    parser.add_argument('--skip-images', type=str, default=None)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_dir = Path(args.source_dir).expanduser()
    if not source_dir.exists() or not source_dir.is_dir():
        raise RuntimeError(f'建标图片目录不存在或不可用：{source_dir}')

    missing_images = build_missing_image_list(source_dir)

    if args.only_images:
        requested = {item.strip() for item in args.only_images.split(',') if item.strip()}
        missing_images = [path for path in missing_images if path.name in requested]

    if args.skip_images:
        skip_set = {item.strip() for item in args.skip_images.split(',') if item.strip()}
        missing_images = [path for path in missing_images if path.name not in skip_set]

    MISSING_MANIFEST_PATH.write_text(
        json.dumps(
            {
                'source_dir': str(source_dir),
                'missing_image_count': len(missing_images),
                'missing_images': [path.name for path in missing_images],
                'only_images': args.only_images,
                'skip_images': args.skip_images,
            },
            ensure_ascii=False,
            indent=2,
        ) + '\n'
    )

    if args.limit is not None:
        missing_images = missing_images[: args.limit]

    api_key = resolve_api_key()
    if not api_key:
        raise RuntimeError('未找到可用 API key。请先在 shell 中设置 COMMERCIAL_DIAGNOSER_API_KEY 或 APIYI_API_KEY。')

    base_url = os.environ.get('COMMERCIAL_DIAGNOSER_BASE_URL', 'https://api.apiyi.com/v1')
    extracted_rules: list[dict[str, Any]] = []
    failed_images: list[dict[str, str]] = []
    processed_page_names = load_processed_page_names()
    if RAW_OUTPUT_PATH.exists():
        extracted_rules = json.loads(RAW_OUTPUT_PATH.read_text())

    for image_path in missing_images:
        try:
            print(f'Processing {image_path.name}...', flush=True)
            parsed_rules = request_rule_extraction(
                image_path=image_path,
                api_key=api_key,
                base_url=base_url,
                timeout_seconds=args.timeout,
            )
            extracted_rules.extend(parsed_rules)
            processed_page_names.add(canonical_image_name(image_path.name))
            RAW_OUTPUT_PATH.write_text(json.dumps(extracted_rules, ensure_ascii=False, indent=2) + '\n')
            save_processed_page_names(processed_page_names)
            print(f'Completed {image_path.name}: {len(parsed_rules)} rules', flush=True)
            time.sleep(2)
        except Exception as exc:
            print(f'Failed {image_path.name}: {exc}', flush=True)
            failed_images.append({'image': image_path.name, 'error': str(exc)})

    SUMMARY_OUTPUT_PATH.write_text(
        json.dumps(
            {
                'base_url': base_url,
                'requested_image_count': len(missing_images),
                'extracted_rule_count': len(extracted_rules),
                'failed_images': failed_images,
                'raw_output_path': str(RAW_OUTPUT_PATH),
                'missing_manifest_path': str(MISSING_MANIFEST_PATH),
            },
            ensure_ascii=False,
            indent=2,
        ) + '\n'
    )

    print(
        json.dumps(
            {
                'requested_image_count': len(missing_images),
                'extracted_rule_count': len(extracted_rules),
                'failed_image_count': len(failed_images),
                'raw_output_path': str(RAW_OUTPUT_PATH),
                'summary_output_path': str(SUMMARY_OUTPUT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == '__main__':
    main()

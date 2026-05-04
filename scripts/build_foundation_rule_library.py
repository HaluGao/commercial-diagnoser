#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / 'data' / 'rules' / 'longfor'
BATCH_FILES = [
    'longfor_first_batch_rules.json',
    'longfor_second_batch_rules.json',
    'longfor_third_batch_rules.json',
    'longfor_fourth_batch_rules.json',
    'longfor_fifth_batch_rules.json',
    'longfor_sixth_batch_rules.json',
]
OUTPUT_FILE = 'longfor_foundation_rules_all.json'


def main() -> None:
    merged_rules = []
    counts = {}

    for filename in BATCH_FILES:
        path = ROOT / filename
        rules = json.loads(path.read_text())
        merged_rules.extend(rules)
        counts[filename] = len(rules)

    output_path = ROOT / OUTPUT_FILE
    output_path.write_text(
        json.dumps(merged_rules, ensure_ascii=False, indent=2) + "\n"
    )

    c2_rules = sum(1 for item in merged_rules if item['source_type'] == 'longfor_c2')
    standard_rules = sum(
        1 for item in merged_rules if item['source_type'] == 'longfor_standard'
    )

    print(
        json.dumps(
            {
                'output_file': str(output_path),
                'file_counts': counts,
                'total_rules': len(merged_rules),
                'c2_rules': c2_rules,
                'standard_rules': standard_rules,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == '__main__':
    main()

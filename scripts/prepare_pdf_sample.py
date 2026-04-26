#!/usr/bin/env python3

import argparse
import json
import subprocess
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def parse_args():
    parser = argparse.ArgumentParser(
        description="Prepare a drawing-heavy PDF sample for the commercial diagnoser."
    )
    parser.add_argument("--input", required=True, help="Path to the source PDF.")
    parser.add_argument("--output-dir", required=True, help="Directory for extracted artifacts.")
    parser.add_argument("--sample-id", required=True, help="Stable sample identifier.")
    parser.add_argument("--project-name", required=True, help="Human-readable project name.")
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_cmd(args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Command failed")


def extract_text(page) -> str:
    return (page.extract_text() or "").strip()


def build_page_title(text: str, page_number: int) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        return lines[0]
    return f"Page {page_number}"


def main():
    args = parse_args()

    input_pdf = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    page_pdf_dir = output_dir / "page_pdfs"
    preview_dir = output_dir / "page_previews"

    ensure_dir(output_dir)
    ensure_dir(page_pdf_dir)
    ensure_dir(preview_dir)

    reader = PdfReader(str(input_pdf))
    pages = []

    for page_index, page in enumerate(reader.pages):
        page_number = page_index + 1
        page_pdf_path = page_pdf_dir / f"page_{page_number:03d}.pdf"
        preview_path = preview_dir / f"page_{page_number:03d}.png"

        writer = PdfWriter()
        writer.add_page(page)
        with page_pdf_path.open("wb") as file_obj:
            writer.write(file_obj)

        run_cmd(
            [
                "sips",
                "-s",
                "format",
                "png",
                str(page_pdf_path),
                "--out",
                str(preview_path),
            ]
        )

        text = extract_text(page)
        page_item = {
            "page_index": page_index,
            "page_number": page_number,
            "page_label": build_page_title(text, page_number),
            "page_pdf_path": str(page_pdf_path),
            "preview_path": str(preview_path),
            "text_chars": len(text),
            "text_excerpt": text[:200],
            "content_profile": "drawing_heavy_page" if len(text) < 80 else "text_mixed_page",
        }
        pages.append(page_item)

    manifest = {
        "sample_id": args.sample_id,
        "project_name": args.project_name,
        "input_pdf_path": str(input_pdf),
        "page_count": len(pages),
        "output_dir": str(output_dir),
        "pages": pages,
    }

    manifest_path = output_dir / "document_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    print(json.dumps({"status": "ok", "manifest_path": str(manifest_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

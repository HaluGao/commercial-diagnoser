#!/usr/bin/env python3

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_args():
    parser = argparse.ArgumentParser(description="Build contact sheets for image review.")
    parser.add_argument("--input-dir", required=True, help="Directory containing images.")
    parser.add_argument("--output-dir", required=True, help="Directory for contact sheets.")
    parser.add_argument("--per-sheet", type=int, default=9, help="Images per sheet.")
    parser.add_argument("--thumb-width", type=int, default=280, help="Thumbnail width.")
    parser.add_argument("--thumb-height", type=int, default=180, help="Thumbnail height.")
    parser.add_argument("--columns", type=int, default=3, help="Column count.")
    return parser.parse_args()


def load_font(size):
    for path in [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def natural_key(path: Path):
    try:
        return int(path.stem)
    except ValueError:
        return path.stem


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def main():
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_dir(output_dir)

    files = sorted(
        [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}],
        key=natural_key,
    )

    font = load_font(18)
    label_height = 36
    cell_width = args.thumb_width
    cell_height = args.thumb_height + label_height
    rows = math.ceil(args.per_sheet / args.columns)

    for sheet_index, start in enumerate(range(0, len(files), args.per_sheet), start=1):
        chunk = files[start : start + args.per_sheet]
        sheet = Image.new(
            "RGB",
            (args.columns * cell_width, rows * cell_height),
            "white",
        )
        draw = ImageDraw.Draw(sheet)

        for idx, image_path in enumerate(chunk):
            row = idx // args.columns
            col = idx % args.columns
            x = col * cell_width
            y = row * cell_height

            image = Image.open(image_path).convert("RGB")
            image.thumbnail((args.thumb_width - 10, args.thumb_height - 10))
            paste_x = x + (args.thumb_width - image.width) // 2
            paste_y = y + 5 + (args.thumb_height - image.height) // 2
            sheet.paste(image, (paste_x, paste_y))

            draw.rectangle(
                [x, y + args.thumb_height, x + cell_width, y + cell_height],
                fill=(245, 245, 245),
            )
            draw.text(
                (x + 10, y + args.thumb_height + 8),
                image_path.name,
                fill="black",
                font=font,
            )

        output_path = output_dir / f"contact_sheet_{sheet_index:02d}.png"
        sheet.save(output_path)
        print(output_path)


if __name__ == "__main__":
    main()

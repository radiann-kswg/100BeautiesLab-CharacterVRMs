"""Compare two Unity captures at the same orthographic scale and neutral pose."""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def compare(before, after, output):
    numbers = (6, 49, 57, 85)
    views = ("front", "side", "back")
    tile, margin, heading, gap = 224, 52, 58, 5
    board = Image.new("RGB", (margin + 6 * tile + 2 * gap, heading + 4 * tile), "#30353d")
    draw = ImageDraw.Draw(board)
    font = ImageFont.truetype("segoeui.ttf", 17)
    title = ImageFont.truetype("segoeuib.ttf", 20)
    for i, view in enumerate(views):
        x = margin + i * (2 * tile + gap)
        draw.text((x + tile, 15), view.title(), fill="white", font=title, anchor="mm")
        for col, (label, root) in enumerate((("Previous", before), ("Revised", after))):
            draw.text((x + (col + .5) * tile, 42), label, fill="white", font=font, anchor="mm")
            for row, number in enumerate(numbers):
                y = heading + row * tile
                frame = root / f"Corefolder-{number}" / f"{view}.png"
                with Image.open(frame) as image:
                    if image.size != (900, 900):
                        raise ValueError(f"Expected a 900 px Unity orthographic capture: {frame}")
                    board.paste(image.convert("RGB").resize((tile, tile), Image.Resampling.LANCZOS),
                                (x + col * tile, y))
                if i == col == 0:
                    draw.text((margin / 2, y + tile / 2), f"#{number}", fill="white", font=font, anchor="mm")
    board.save(output)


if __name__ == "__main__":
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("previous", type=Path)
    args.add_argument("revised", type=Path)
    args.add_argument("--out", type=Path, default=Path(__file__).with_name("volume-revision.png"))
    options = args.parse_args()
    compare(options.previous, options.revised, options.out)

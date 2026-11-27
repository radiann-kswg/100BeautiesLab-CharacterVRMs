"""Pair each canonical VRM with that character's own official Corefolder illustration."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from compare_corefolder_art import normalize

# Prefer an upright Corefolder drawing. The camera turns in the same direction
# as the illustrated face. A neutral VRM retains its original rest posture.
PAIRS = ((4,1,0), (16,2,18), (20,2,0), (22,1,9), (25,1,9), (93,1,27))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    db = args.db / "data/Works_NumberTales"
    records = {str(e["Num"]):e for e in json.loads((db/"DataBases/db_Primary.json").read_text(encoding="utf-8-sig"))}
    references = {s["id"]:s for s in json.loads((HERE.parent/"style-training/source-vrms.json").read_text(encoding="utf-8-sig"))}
    tile, left, header = 246, 68, 37
    heads = ("Official Corefolder", "VRM facing artwork", "VRM front", "VRM side", "VRM back")
    sheet = Image.new("RGB",(left+len(heads)*tile, header+len(PAIRS)*tile),"#30353d")
    pen = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("segoeui.ttf",18)
    for col, title in enumerate(heads):
        pen.text((left+tile*(col+.5),header/2), title, anchor="mm", font=font, fill="white")
    pairs = []
    for row,(number,variant,yaw) in enumerate(PAIRS):
        art = db / f"Images/DB_Primary/corefolder/{number}/emstk_corefolderNTS-{number}-{variant}.png"
        folder = args.captures / f"Corefolder-{number}"
        capture = json.loads((folder/"unity.json").read_text())
        reference = references[number]
        if capture["sha256"] != reference["sha256"] or capture["number"] != number:
            raise ValueError(f"Unmatched VRM capture: #{number}")
        images = [art,folder/f"angle{yaw}.png",folder/"front.png",folder/"side.png",folder/"back.png"]
        pen.text((left/2,header+(row+.5)*tile),f"#{number}",anchor="mm",font=font,fill="white")
        for col, path in enumerate(images):
            # Illustration and matched view are scaled to compare the design.
            # All three technical views retain the same world-scale camera.
            im = normalize(path,tile-2)[0] if col<2 else Image.open(path).convert("RGB").resize((tile-2,tile-2),Image.Resampling.LANCZOS)
            sheet.paste(im,(left+col*tile,header+row*tile))
        pairs.append(dict(number=number, name=records[str(number)]["Name_JP"], referenceVRM=reference,
                          illustration=art.relative_to(db).as_posix(), illustrationSHA256=hashlib.sha256(art.read_bytes()).hexdigest(),
                          matchedYaw=yaw, orthoHalfHeightM=capture["orthographicSize"], shader=capture["shader"]))
    args.out.mkdir(parents=True,exist_ok=True)
    sheet.save(args.out/"reference-pairs.png")
    (args.out/"reference-pairs.json").write_text(json.dumps(pairs,indent=2,ensure_ascii=False)+"\n",encoding="utf8")


if __name__ == "__main__":
    main()

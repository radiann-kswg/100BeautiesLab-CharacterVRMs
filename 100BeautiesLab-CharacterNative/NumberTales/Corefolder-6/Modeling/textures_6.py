"""Prepare Mui's packed image maps from the official corefolder art and starter UV atlas."""
import argparse
from pathlib import Path
from eye_art import cheek_detail, prepare_eye_map

import numpy as np
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
NATIVE = HERE.parents[1]
DEFAULT_DB = Path("D:/VisualStudio Code Userfile/100BeautiesLab_CreationsDB")


def face_atlas(out):
    """Keep the donor blink/lip/blush UVs, replace the iris and remove the cyan backing."""
    im = Image.open(NATIVE / "Corefolder-4/CoreFolder-4.png").convert("RGBA")
    pixels = np.array(im)
    r, g, b = np.moveaxis(pixels[:, :, :3].astype(float), -1, 0)
    cyan = (g - r > 9) & (b - r > 9)
    pixels[cyan, :3] = 255
    # The two independently mapped official eyes include their own catchlights.
    pixels[865:1024, 753:897, 3] = 0
    pixels[872:, 898:, 3] = 0
    im = Image.fromarray(pixels)
    cheek_detail(im,6)
    # The two halves of the upper lip share UVs. Ink follows the existing animated lip rim.
    lip=im.crop((15,151,50,176)).resize((280,200),Image.Resampling.BICUBIC)
    pen=ImageDraw.Draw(lip)
    lip_edge=[(20.6,167.2),(24,166.9),(27.5,166.4),(31,165.4),(35.2,164),(38.8,162.1)]
    pen.line([(round((x-15)*8),round((y-151)*8)) for x,y in lip_edge],fill="#594552",width=16,joint="curve")
    im.paste(lip.resize((35,25),Image.Resampling.LANCZOS),(15,151))
    im.save(out / "Mui-Face.png", optimize=True)


def fur_map(out):
    """A symmetric curved white bib with its warm pink narrow transition, as on art 1."""
    h, w = 512, 1024
    y, x = np.mgrid[0:h, 0:w]
    height = .713*(1-(y+.5)/h)
    # The #16 front fur is widest at the waist and rounds back into the
    # flank near the floor. Use its measured section angles with Mui's bib.
    levels = [.009,.018,.033,.060,.100,.160,.250,.370,.460,.510,.575,.630,.713]
    angles = [0,.23,.37,.51,.58,.63,.68,.69,.67,.65,.63,.61,.61]
    half_angle = np.sqrt(np.interp(height, levels, np.square(angles)))
    a = np.abs(((x+.5)/w - .5)*2*np.pi)
    def smooth(t): return np.clip(t,0,1)[...,None]
    blend_at_foot = smooth((height-.009)/.006)
    blush = smooth((half_angle+.031-a)/.018)*blend_at_foot
    belly = smooth((half_angle-a)/.013)*blend_at_foot
    base = (1-blush)*np.array([255,118,162]) + blush*np.array([255,185,207])
    color = (1-belly)*base + belly*255
    Image.fromarray(np.uint8(np.round(color))).save(out / "Mui-Fur.png", optimize=True)


def prepare(database, out):
    out.mkdir(exist_ok=True, parents=True)
    face_atlas(out)
    fur_map(out)
    band = Image.new("RGB",(256,128))
    paint = ImageDraw.Draw(band)
    for y in range(128):
        edge = np.clip(((y+.5)/128-.76)/.24,0,1)**1.4
        for start,end,base,shade in ((0,127,(255,206,237),(235,167,208)),(128,255,(255,118,162),(227,88,140))):
            rgb=np.round(np.array(base)*(1-edge)+np.array(shade)*edge).astype(int)
            paint.line((start,y,end,y),fill=tuple(rgb))
    band.save(out/"Mui-TailBand.png", optimize=True)
    image_root = database / "data/Works_NumberTales/Images/DB_Primary"
    prepare_eye_map(6, out / "Mui-Eyes.png")
    art = Image.open(image_root / "corefolder/6/emstk_corefolderNTS-6-1.png").convert("RGBA")
    art.crop((753,590,909,791)).save(out / "Mui-Brooch.png", optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    prepare(args.database, args.out)

"""Prepare Mui's packed image maps from the official corefolder art and starter UV atlas."""
import argparse
from pathlib import Path
from eye_art import prepare_eye_map
from scipy import ndimage

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
    # The original uses a large airbrush spot. Mui's pose 1 uses four short cheek hatches.
    swatch = Image.new("RGB",(840,1140),"white")
    hatches = ImageDraw.Draw(swatch)
    for x,y in ((79,162),(88,165),(97,168),(106,171)):
        hatches.line((4*(x-3),4*(y+3),4*(x+4),4*(y-4)), fill="#eca386", width=6)
    swatch = swatch.resize((210,285),Image.Resampling.LANCZOS)
    im.paste(swatch.crop((50,137,139,196)),(50,137))
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
    z = 1 - (y + .5)/h
    half_angle = np.interp(z, [0,.08,.20,.42,.58,.75,1],
                            [.77,.77,.70,.59,.55,.58,.65])
    a = np.abs(((x+.5)/w - .5)*2*np.pi)
    def smooth(t): return np.clip(t,0,1)[...,None]
    blush = smooth((half_angle+.038-a)/.014)
    belly = smooth((half_angle-a)/.012)
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
    prepare_eye_map(6, image_root, out / "Mui-Eyes.png")
    art = Image.open(image_root / "corefolder/6/emstk_corefolderNTS-6-1.png").convert("RGBA")
    art.crop((753,590,909,791)).save(out / "Mui-Brooch.png", optimize=True)
    # Undo the illustrated head roll and scale the drawing by its eye separation.
    # Only pixels from the pink hair range are transferred. Eyelashes, face and cheek marks
    # continue to come from the animated face mesh behind the fringe.
    ny,nx=416,736
    yy,xx=np.mgrid[:ny,:nx]
    local_x=(xx+.5)/nx*.60-.30
    local_z=1.062-(yy+.5)/ny*.254
    angle=np.deg2rad(8)
    sx=(831+1170*(local_x*np.cos(angle)+(local_z-.837)*np.sin(angle))).round().astype(int)
    sy=(384+1170*(local_x*np.sin(angle)-(local_z-.837)*np.cos(angle))).round().astype(int)
    sample=np.asarray(art)[sy,sx].astype(float)
    red,green,blue=sample[:,:,:3].transpose(2,0,1)
    coverage=np.clip((red-green-38)/38,0,1)*np.clip((blue-green-13)/18,0,1)
    coverage*=np.clip((red-87)/60,0,1)
    # In the drawing the black brow crosses the pink bang. Keep the mesh brow
    # behind the fringe and restore the few pink pixels occupied by the drawn line.
    band=(abs(local_x)<.18)&(abs(local_x)>.028)&(local_z>.875)&(local_z<.926)
    fill=band&ndimage.binary_closing(coverage>.45,iterations=7)&(coverage<.45)
    sample[fill,:3]=[255,118,162]
    coverage[fill]=1
    sample[:,:,3]=255*coverage
    # Edge bleed is pink rather than black or skin when the alpha mip levels are sampled.
    sample[:,:,:3]=np.where((coverage>.07)[:,:,None],sample[:,:,:3],[255,118,162])
    Image.fromarray(np.uint8(sample)).save(out/"Mui-Bangs.png",optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    prepare(args.database, args.out)

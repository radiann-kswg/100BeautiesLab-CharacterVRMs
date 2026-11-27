"""Build fixed-scale Unity comparisons of the head and coloured torso plus official art crops."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REFS = (4,16,20,22,25,93)
TARGETS = (6,49,57,85)
# Box in each drawing's opaque bounding rectangle, including the ears and side hair.
CROPS = {4:(.14,-.01,.84,.50),16:(.05,-.01,.84,.63),20:(.18,-.01,.87,.55),
         22:(.26,-.02,.80,.63),25:(.14,-.01,.92,.61),93:(.22,-.01,.90,.57),
         6:(.24,-.01,.87,.55),49:(.17,-.01,.83,.53),57:(.05,-.01,.92,.58),85:(.21,-.01,.88,.54)}
YAW = {4:30,16:30,20:30,22:30,25:30,93:30,6:30,49:-30,57:30,85:30}


def drawing(db,n,tile):
    variant = 2 if n in (16,20,57) else 1
    src = db/f"data/Works_NumberTales/Images/DB_Primary/corefolder/{n}/emstk_corefolderNTS-{n}-{variant}.png"
    with Image.open(src) as im:
        rgba = im.convert("RGBA")
        orig = rgba.crop(rgba.getbbox())
    a,b,c,d = CROPS[n]
    crop = orig.crop((round(a*orig.width),round(b*orig.height),round(c*orig.width),round(d*orig.height)))
    crop.thumbnail((tile-12,tile-12),Image.Resampling.LANCZOS)
    panel = Image.new("RGB",(tile,tile),"#bfbfbf")
    panel.paste(crop,((tile-crop.width)//2,(tile-crop.height)//2),crop)
    return panel


def photo(directory,n,stem,tile,box=None):
    with Image.open(directory/f"Corefolder-{n}"/f"{stem}.png") as im:
        part = im.convert("RGB")
        if box:
            part = part.crop(box)
        return part.resize((tile,tile),Image.Resampling.LANCZOS)


def sheet(rows,columns,make_tile,path,tile=208):
    left,head = 54,39
    image = Image.new("RGB",(left+tile*len(columns),head+tile*len(rows)),"#30353d")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("meiryo.ttc",16)
    for col,label in enumerate(columns):
        draw.text((left+(col+.5)*tile,head/2),label,fill="white",font=font,anchor="mm")
    for row,n in enumerate(rows):
        y = head+row*tile
        draw.text((left/2,y+tile/2),f"#{n}",fill="white",font=font,anchor="mm")
        for col in range(len(columns)):
            image.paste(make_tile(n,col,tile),(left+col*tile,y))
    image.save(path)


def contours(data,path):
    levels = np.asarray(data["levels_mm"])
    records = data["records"]
    values = {n:np.asarray(r["support_mm"]) for n,r in records.items()}
    median = np.median([values[n] for n in data["reference_ids"]],axis=0)
    board = Image.new("RGB",(1080,530),"#f5f6f5")
    pen = ImageDraw.Draw(board)
    font = ImageFont.truetype("meiryo.ttc",16)
    small = ImageFont.truetype("meiryo.ttc",13)
    scale = .46
    def outline(support,i,cx,color,width):
        pos,neg = cx+support[:,i]*scale,cx-support[:,i+8]*scale
        y = 409-scale*levels
        pen.line(list(zip(pos,y)),fill=color,width=width)
        pen.line(list(zip(neg,y)),fill=color,width=width)
    for i,cx,title in ((0,274,"正面"),(4,814,"側面")):
        pen.text((cx,27),title,font=font,fill="#1c2a35",anchor="mm")
        for mm in (100,250,360,510,630):
            y = 409-mm*scale
            pen.line((cx-218,y,cx+218,y),fill="#dce0df")
            pen.text((cx-222,y),str(mm),font=small,fill="#566169",anchor="rm")
        outline(values["Base"],i,cx,"#e1a13a",4)
        outline(median,i,cx,"#4c74ad",4)
        for n in TARGETS:
            outline(values[str(n)],i,cx,"#213d3c",1)
    pen.text((36,448),"地上高 mm　／　70断面を同一の世界座標で計測",fill="#34434a",font=font)
    for x,label,color in ((36,"共通素体","#e1a13a"),(275,"規範6体の中央値","#4c74ad"),(630,"制作4体（輪郭が重なる）","#213d3c")):
        pen.line((x,497,x+34,497),fill=color,width=4)
        pen.text((x+43,497),label,fill="#34434a",font=font,anchor="lm")
    board.save(path)


def silhouettes(previous, current, path):
    cell_w,cell_h = 284,228
    image = Image.new("RGB",(72+3*cell_w,80+4*cell_h),"#f5f6f5")
    pen = ImageDraw.Draw(image)
    font = ImageFont.truetype("meiryo.ttc",16)
    for j,(color,label) in enumerate((("#515c63","共通の輪郭"),("#c54f32","修正前のみに見える部分"),("#258a9b","修正後のみに見える部分"))):
        x = 72+j*cell_w
        pen.rectangle((x+10,11,x+28,28),fill=color)
        pen.text((x+36,20),label,font=font,anchor="lm",fill="#23313b")
    for col,(angle,label) in enumerate(((0,"正面"),(30,"斜め30°"),(90,"側面"))):
        pen.text((72+(col+.5)*cell_w,58),label,font=font,anchor="mm",fill="#23313b")
        for row,n in enumerate(TARGETS):
            with np.load(previous/f"{n}.npz") as a, np.load(current/f"{n}.npz") as b:
                old,new = a[str(angle)],b[str(angle)]
            rgb = np.full((*new.shape,3),[235,237,237],dtype=np.uint8)
            rgb[new&old] = (81,92,99)
            rgb[old&~new] = (197,79,50)
            rgb[new&~old] = (37,138,155)
            x,y = 72+col*cell_w,80+row*cell_h
            image.paste(Image.fromarray(rgb),(x,y))
            if col==0:
                pen.text((36,y+cell_h/2),f"#{n}",font=font,anchor="mm",fill="#23313b")
    image.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("db","refs","previous","current","torso_previous"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--out",default=HERE,type=Path)
    parser.add_argument("--mask-before",type=Path)
    parser.add_argument("--mask-after",type=Path)
    args = parser.parse_args()
    def ref_tile(n,col,t):
        if col==0:
            return drawing(args.db,n,t)
        return photo(args.refs,n,["","head0",f"head{YAW[n]}","head90","head180"][col],t)
    sheet(REFS,("本人の原画","規範・正面","斜め30°","側面","背面"),ref_tile,args.out/"heads-reference.png")
    def target_tile(n,col,t):
        if col==0:
            return drawing(args.db,n,t)
        if col==1:
            return photo(args.previous,n,"head0",t)
        return photo(args.current,n,["","","head0",f"head{YAW[n]}","head-90","head90"][col],t)
    sheet(TARGETS,("本人の原画","修正前の正面","修正後の正面","斜め","側面 −90°","側面 +90°"),
          target_tile,args.out/"heads-revision.png")
    body_box = (120,216,780,876)
    def torso(n,col,t):
        name = ("torso-front","torso-front","torso-body-front","torso-body-front","torso-side","torso-side")[col]
        return photo(args.torso_previous if col%2==0 else args.current,n,name,t,body_box)
    sheet(TARGETS,("正面・修正前","正面・修正後","胴・修正前","胴・修正後","側面・修正前","側面・修正後"),
          torso,args.out/"torso-comparison.png")
    wardrobe = ("core-front","core-side","core-back","undressed-front","dressed-front","dressed-side","dressed-back")
    sheet(TARGETS,("素体・正面","素体・側面","素体・背面","髪・耳・尾を表示","着衣・正面","着衣・側面","着衣・背面"),
          lambda n,col,t:photo(args.current,n,wardrobe[col],t),args.out/"wardrobe.png",194)
    contours(json.loads((args.out/"torso-profiles.json").read_text(encoding="utf8")),args.out/"torso-contours.png")
    if args.mask_before and args.mask_after:
        silhouettes(args.mask_before,args.mask_after,args.out/"head-silhouettes.png")


if __name__=="__main__":
    main()

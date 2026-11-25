"""Compare official drawing 2 with the old and revised VRMs in the same camera."""
from argparse import ArgumentParser
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"Corefolder-6/Modeling"))
from fit_report_6 import aligned_mask,normalize


def measurements(image):
    d=np.asarray(image)
    h,w=d.shape[:2]
    y,x=np.mgrid[:h,:w]
    rgb=d[:,:,:3].astype(float)
    red,green,blue=rgb.transpose(2,0,1)
    valid=d[:,:,3]>180
    # The original mark and its two olive piping strokes share one material in drawing 2.
    olive=valid&(green-red>9)&(red-blue>55)&(green>115)&(red<226)&(blue<108)
    band=olive&(x<.565*w)&(y>.40*h)&(y<.72*h)
    by,bx=np.where(band)
    iris=olive&(x>.51*w)&(x<.92*w)&(y>.22*h)&(y<.44*h)
    iy,ix=np.where(iris)
    return {
        "width_over_height":round(w/h,4),
        "armband_olive_center_y":round(by.mean()/h,4) if len(by)>15 else None,
        "armband_olive_width_over_height":round((bx.max()-bx.min()+1)/h,4) if len(bx)>15 else None,
        "olive_iris_area_over_silhouette":round(len(ix)/valid.sum(),5),
        "olive_iris_center_y":round(iy.mean()/h,4) if len(iy)>15 else None,
    }


if __name__=="__main__":
    parser=ArgumentParser()
    for name in ("official","before","after","out"):
        parser.add_argument("--"+name,required=True,type=Path)
    args=parser.parse_args()
    titles=("Official corefolder art 2","Previous Refined VRM","Revised VRM")
    images=[normalize(p) for p in (args.official,args.before,args.after)]
    w=max(im.width for im in images)
    masks=[aligned_mask(im,w) for im in images]
    board=Image.new("RGB",(3*(w+30),664),"#eeeef0")
    d=ImageDraw.Draw(board)
    try:font=ImageFont.truetype("segoeui.ttf",24)
    except OSError:font=ImageFont.load_default()
    metrics={}
    for i,(title,im,mask) in enumerate(zip(titles,images,masks)):
        left=i*(w+30)+(w+30-im.width)//2
        board.paste(im,(left,48),im)
        d.text((left,8),title,font=font,fill="#292b30")
        metrics[title]=measurements(im)
        metrics[title]["silhouette_IoU_with_art"]=round(float((mask&masks[0]).sum()/(mask|masks[0]).sum()),4)
    args.out.mkdir(parents=True,exist_ok=True)
    board.save(args.out/"Fit-Fivens.png",optimize=True)
    (args.out/"Fit-Fivens.json").write_text(json.dumps(metrics,indent=2)+"\n",encoding="utf-8")

"""Compare a neutral, uniformly lit VRM capture with transparent official artwork."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def normalize(path, size=390):
    """Center the subject, preserving aspect. The largest dimension takes 94% of the frame."""
    image = Image.open(path).convert("RGBA")
    rgb = np.asarray(image).astype(np.int16)
    if np.any(rgb[:, :, 3] < 32):
        mask = rgb[:, :, 3] >= 128
    else:
        bg = np.median(np.concatenate((rgb[0, :, :3], rgb[-1, :, :3])),axis=0)
        mask = np.max(abs(rgb[:, :, :3]-bg),axis=2) > 9
    matte = Image.fromarray(mask.astype(np.uint8)*255)
    box = matte.getbbox()
    if not box:
        raise ValueError(f"No subject in {path}")
    image = image.convert("RGB").crop(box); matte = matte.crop(box)
    dims = tuple(max(1,round(k*size*.94/max(image.size))) for k in image.size)
    xy = ((size-dims[0])//2,(size-dims[1])//2)
    content = image.resize(dims,Image.Resampling.LANCZOS)
    alpha = matte.resize(dims,Image.Resampling.NEAREST)
    board = Image.new("RGB",(size,size),(192,192,192)); board.paste(content,xy,alpha)
    canvas = Image.new("L",(size,size));canvas.paste(alpha,xy)
    return board, np.asarray(canvas)>0, (box[2]-box[0])/(box[3]-box[1])


def compare(reference,before,after,output):
    imgs,masks,ratios = zip(*(normalize(p) for p in (reference,before,after)))
    ref,old,new=masks
    def metrics(other,ratio):
        union=np.count_nonzero(ref|other)
        rows=np.linspace(0,other.shape[0],9,dtype=int)
        return {"silhouetteIoU":round(float(np.count_nonzero(ref&other)/union),4),
                "widthToHeight":round(ratio,3),
                "occupancyDeltaByHorizontalEighth":[round(float(other[a:b].mean()-ref[a:b].mean()),3) for a,b in zip(rows,rows[1:])]}
    delta=np.full((*ref.shape,3),[192,192,192],np.uint8)
    delta[ref&new]=[240,240,240];delta[ref&~new]=[50,130,210];delta[new&~ref]=[219,111,57]
    sheet=Image.new("RGB",(390*4,430),(44,49,55));draw=ImageDraw.Draw(sheet)
    try:font=ImageFont.truetype("segoeui.ttf",20)
    except OSError:font=ImageFont.load_default()
    for i,(lab,img) in enumerate(zip(("Official","Before","After","Silhouette overlap"),[*imgs,Image.fromarray(delta)])):
        sheet.paste(img,(390*i,40));draw.text((390*(i+.5),19),lab,anchor="mm",font=font,fill="white")
    sheet.save(output)
    return {"referenceWidthToHeight":round(ratios[0],3),"before":metrics(old,ratios[1]),"after":metrics(new,ratios[2])}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("reference","before","after","output"):p.add_argument(name,type=Path)
    a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
    result=compare(a.reference,a.before,a.after,a.output)
    print(json.dumps(result,indent=2))

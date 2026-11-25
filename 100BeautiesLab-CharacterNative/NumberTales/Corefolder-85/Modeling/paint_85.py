"""UV artwork for Hakko. The base values come from the official NumberTales palette."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

HERE=Path(__file__).resolve().parent


def lit_swatch(color,factor=.77):
    a=np.array(color,dtype=float)/255
    lin=np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)*factor
    return tuple(np.rint(255*np.where(lin<=.0031308,12.92*lin,1.055*lin**(1/2.4)-.055)).astype(int))


def paint():
    size=1024
    y,x=np.mgrid[:size,:size]
    v=1-y/(size-1)
    brown=lit_swatch((196,132,85))
    edge=lit_swatch((175,113,75))
    base=np.empty((size,size,3),np.uint8)
    base[:]=brown
    border=np.interp(v,[0,.08,.25,.49,.70,.86,1],[.46,.52,.525,.49,.455,.46,.52])
    longitude=abs(2*np.pi*(x/(size-1)-.5))
    base[longitude<border+.021]=edge
    base[longitude<border]=(255,255,253)
    Image.fromarray(base,'RGB').save(HERE/'85-body.png')
    seam=.09+.37*v**1.4
    base[:]=brown;base[x/1023<seam+.012]=edge;base[x/1023<seam]=(255,255,253)
    Image.fromarray(base,'RGB').resize((256,256)).save(HERE/'85-neck.png')
    # The tapered warm edge follows the loft UVs, ending with each strand.
    u=x/(size-1)
    mid=.410+.018*np.sin(v*np.pi*1.3)
    thick=.054*np.sin(np.pi*np.clip(v,.001,.999))**.65
    base[:]=brown
    base[abs(u-mid)<thick]=lit_swatch((175,110,69))
    base[abs(u-mid)<thick*.22]=lit_swatch((139,91,62))
    Image.fromarray(base,'RGB').resize((256,256),Image.Resampling.LANCZOS).save(HERE/'85-hair.png')

    # UV longitude follows the conical ear. The golden inner tuft is painted
    # into the same closed shell and turns continuously with its curvature.
    for side,uc in [('R',.384),('L',.505)]:
        base[:]=brown
        u=x/(size-1)
        mid=uc+.102*(v-.55)
        oval=np.sqrt(np.maximum(0,1-((v-.56)/.53)**2))
        opening=(abs(u-mid)<.116*oval)&(v>.08)
        rim=(abs(u-mid)<.121*oval)&(v>.073)
        base[rim]=lit_swatch((118,83,59))
        base[opening]=(255,254,245)
        ear=Image.fromarray(base,'RGB')
        draw=ImageDraw.Draw(ear)
        offsets=[(-.084,.491),(-.078,.53),(-.080,.592),(-.065,.578),(-.037,.57),
                 (-.002,.576),(.039,.60),(.057,.603),(.073,.579),(.079,.546),
                 (.074,.52),(.087,.505),(.072,.495),(.056,.476),(.025,.45),(-.012,.445),(-.061,.461)]
        draw.polygon([((uc+du)*1023,(1-h)*1023) for du,h in offsets],fill=lit_swatch((239,157,70)))
        folded=[(-.132,.91),(-.112,.839),(-.094,.765),(-.080,.678),(-.082,.599),
                (-.101,.513),(-.115,.475),(-.140,.46)]
        draw.polygon([((uc+du)*1023,(1-h)*1023) for du,h in folded],fill=brown)
        ear.resize((512,512),Image.Resampling.LANCZOS).save(HERE/f'85-ear-{side}.png')

    ori=Image.open(HERE.parents[1]/'Corefolder-4/CoreFolder-4.png').convert('RGBA')
    a=np.array(ori)
    r,g,b=np.moveaxis(a[:,:,:3].astype(float),-1,0)
    color=(g>r+9)&(b>r+9)
    a[color,:3]=255
    iris=(x>750)&(x<897)&(y>865)&color
    a[iris&(r<125),:3]=(0,141,170)
    a[iris&(r>=125),:3]=(112,218,226)
    a[865:1024,899:1024,:]=0
    a[(x<202)&(y<238),:3]=255
    face=Image.fromarray(a,'RGBA')
    draw=ImageDraw.Draw(face)
    draw.ellipse((773,873,889,1008),outline=(25,65,75,255),width=4)
    for cx in (81,95,108):
        draw.line((cx-2,170,cx+4,163),fill=(222,183,147,255),width=2)
    draw.ellipse((846,897,861,911),fill=(255,255,248,255))
    face.save(HERE/'85-face.png')


if __name__=='__main__':
    paint()

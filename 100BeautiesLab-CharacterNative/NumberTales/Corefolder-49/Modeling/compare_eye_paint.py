"""Compare both eyes, mouth and chin at the fixed artwork yaw of #49 or #85."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from compare_49 import cell, components, frame


def iris_pair(image, number):
    a=np.asarray(image,dtype=int)
    r,g,b=a[:,:,:3].transpose(2,0,1)
    y=np.arange(image.height)[:,None]
    if number==49:
        color=(b-r>60)&(b-g>40)&(g<146)&(r<120)
        band=(y>85)&(y<163)
    else:
        color=(g-r>44)&(b-r>55)&(g>98)&(g>b-50)
        band=(y>115)&(y<217)
    pair=components(color&band&(a[:,:,3]>190),8)[:2]
    if len(pair)!=2:
        raise ValueError(f'Could not isolate both irises for #{number}')
    return sorted(pair,key=lambda box:box['cx'])


def compare(number,db,strip,slot,angle,out):
    art=db/'data/Works_NumberTales/Images/DB_Primary/corefolder'/str(number)
    pictures=[frame(Image.open(art/f'emstk_corefolderNTS-{number}-{i}.png').convert('RGBA')) for i in (1,2)]
    pictures.append(cell(Image.open(strip).convert('RGBA'),slot))
    labels=['Official 1','Official 2',f'VRM {angle:+g} deg']
    canvas=Image.new('RGB',(390*3,252),'#E6E8EB')
    pen=ImageDraw.Draw(canvas)
    try: font=ImageFont.truetype('segoeui.ttf',18)
    except OSError: font=ImageFont.load_default()
    metrics={}
    for i,(image,title) in enumerate(zip(pictures,labels)):
        a,b=iris_pair(image,number)
        midx=(a['cx']+b['cx'])/2
        midy=(a['cy']+b['cy'])/2
        box=(round(midx)-105,round(midy)-49,round(midx)+105,round(midy)+67)
        crop=image.crop(box).resize((380,210),Image.Resampling.LANCZOS)
        canvas.paste(crop,(i*390+5,35),crop)
        pen.text((i*390+10,6),title,fill='#28353E',font=font)
        metrics[title]={'screen_left':a,'screen_right':b,'center_distance_px':round(b['cx']-a['cx'],2),
                        'image_height_px':image.height}
    out.mkdir(parents=True,exist_ok=True)
    canvas.save(out/'eyes-and-chin.png')
    (out/'eyes-and-chin.json').write_text(json.dumps(metrics,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:[v['center_distance_px'],v['screen_left']['w'],v['screen_right']['w']] for k,v in metrics.items()}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('number',type=int,choices=[49,85])
    p.add_argument('db',type=Path)
    p.add_argument('strip',type=Path)
    p.add_argument('slot',type=int)
    p.add_argument('angle',type=float)
    p.add_argument('out',type=Path)
    args=p.parse_args()
    compare(args.number,args.db,args.strip,args.slot,args.angle,args.out)

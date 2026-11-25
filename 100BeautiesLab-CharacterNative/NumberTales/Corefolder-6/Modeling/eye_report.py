"""Compare the independently observed eyes with frontal renders of the actual VRMs."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from scipy import ndimage

from eye_art import EYES


def panel(image, size=(186,138)):
    rgb=Image.new('RGB',image.size,'#eeeeef')
    rgb.paste(image,mask=image.getchannel('A'))
    return ImageOps.contain(rgb,size,Image.Resampling.LANCZOS)


def render_eye(image,n,j):
    return image.crop((186+213*j,299,316+213*j,445))


def blue_x(image,number):
    r,g,b,_=np.asarray(image).astype(float).transpose(2,0,1)
    mask=(b-r>15)&(b-g>6) if number==6 else (b-r>20)&(b-g>12)
    blobs,_=ndimage.label(mask)
    keep=1+np.argmax(np.bincount(blobs.ravel())[1:])
    return np.where(blobs==keep)[1].mean()


def landmarks(image):
    r,g,b,a=np.asarray(image).astype(float).transpose(2,0,1)
    y,x=np.mgrid[:256,:256]
    white=(r>225)&(g>225)&(b>225)&(a>195)&(x>128)&(y<151)
    blobs,count=ndimage.label(white)
    positions=[]
    for blob in range(1,count+1):
        ys,xs=np.where(blobs==blob)
        if len(xs)>50 and xs.mean()>158:positions.append((len(xs),xs.mean(),ys.mean()))
    _,cx,cy=max(positions)
    return {'upper_right_glint_xy_cell_fraction':[round(float(cx/256),3),round(float(cy/256),3)]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--number',type=int,choices=[6,57],required=True)
    for name in ('official-root','before','neutral','gaze','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    n=args.number
    source=Image.open(args.out/('Mui-Eyes.png' if n==6 else 'Fivens-Eyes.png')).convert('RGBA')
    renders=[Image.open(file).convert('RGBA') for file in (args.before,args.neutral,args.gaze)]
    board=Image.new('RGB',(837,395),'#f1f2f4')
    pen=ImageDraw.Draw(board)
    font=ImageFont.truetype('segoeui.ttf',17)
    small=ImageFont.truetype('segoeui.ttf',14)
    for i,label in enumerate(('Official drawing','Previous VRM','Revised VRM','Both eye bones +8 deg')):
        pen.text((8+i*208,7),label,fill='#282a2c',font=font)
    report={'vrm_sha256':hashlib.sha256((args.out/f'Corefolder-{n}.vrm').read_bytes()).hexdigest(),
            'camera':'Reimported VRM, frontal orthographic 0.70 m, 720 x 720, neutral pose.',
            'source_order':'screen left, screen right','eyes':[]}
    for j,(file,_,points) in enumerate(EYES[n]):
        xy=np.array(points)
        lo,hi=xy.min(axis=0),xy.max(axis=0)
        pad=np.ceil((hi-lo)*.19).astype(int)
        with Image.open(args.official_root/file) as art:
            crop=art.crop((*map(int,lo-pad),*map(int,hi+pad))).convert('RGBA')
        eyes=[render_eye(im,n,j) for im in renders]
        panels=[crop,*eyes]
        for i,im in enumerate(panels):
            tile=panel(im)
            board.paste(tile,(i*208+(208-tile.width)//2,40+j*159))
        cell=source.crop((256*j,0,256*(j+1),256))
        sample=landmarks(cell)
        sample['official_image']=file
        sample['rendered_gaze_displacement_px']=round(float(blue_x(eyes[2],n)-blue_x(eyes[1],n)),3)
        report['eyes'].append(sample)
    pen.text((10,361),f'#{n}   Top: screen left eye.  Bottom: screen right eye.   Identical framing in all three VRM columns.',font=small,fill='#36393b')
    board.save(args.out/'Eye-Fit.png',optimize=True)
    (args.out/'Eye-Fit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()

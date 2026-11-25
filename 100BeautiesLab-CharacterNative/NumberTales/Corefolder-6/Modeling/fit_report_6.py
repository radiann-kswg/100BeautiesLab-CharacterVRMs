"""Compare registered render silhouettes and palette landmarks to official corefolder pose 1."""
from argparse import ArgumentParser
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage


def normalize(path):
    image=Image.open(path).convert("RGBA")
    bounds=image.getchannel("A").point(lambda v: 255 if v>127 else 0).getbbox()
    image=image.crop(bounds)
    return image.resize((round(600*image.width/image.height),600),Image.Resampling.LANCZOS)


def components(mask,size):
    lab,n=ndimage.label(mask)
    return [np.where(lab==i) for i in range(1,n+1) if np.count_nonzero(lab==i)>=size]


def measure(im):
    d=np.asarray(im)
    h,w=d.shape[:2]
    y,x=np.mgrid[:h,:w]
    u,v=x/w,y/h
    rgb=d[:,:,:3].astype(float)
    valid=d[:,:,3]>180
    def near(color,tol):
        return valid&(np.linalg.norm(rgb-color,axis=2)<tol)
    face=components(near((255,255,255),16)&(u>.28)&(u<.86)&(v>.15)&(v<.445),200)
    fy,fx=max(face,key=lambda item:len(item[0]))
    eyes=near((163,133,171),30)&(v>.15)&(v<.374)
    eyelines=[]
    for region in ((u>.30)&(u<fx.mean()/w), (u>=fx.mean()/w)&(u<.83)):
        yy,xx=max(components(eyes&region,40),key=lambda item:len(item[0]))
        eyelines.append(yy.mean()/h)
    cy,cx=np.where(near((25,94,189),47)&(v>.38)&(v<.79)&(u>.35)&(u<.76))
    collars=components(near((106,166,215),30)&(v>.24)&(v<.70),1200)
    bands=np.concatenate([part[0] for part in collars])
    tips=near((255,206,237),31)&((u<.265)|(u>.755))&(v>.155)
    ey,ex=np.where(near((255,253,242),8)&(u>.30)&(u<.83)&(v<.24))
    return {k:round(float(z),4) for k,z in {
        "width_over_height":w/h,
        "screen_left_iris_y":eyelines[0],"screen_right_iris_y":eyelines[1],
        "white_face_and_cheeks_width_over_height":(fx.max()-fx.min()+1)/h,
        "lower_cheek_y":fy.max()/h,
        "collar_lower_y_p99":np.percentile(bands,99)/h,
        "sapphire_brooch_y":cy.mean()/h,
        "exposed_cream_ear_area_over_silhouette":len(ey)/valid.sum(),
        "exposed_pale_tail_tip_area_over_silhouette":tips.sum()/valid.sum(),
        "tail_tips_y_centroid":y[tips].mean()/h
    }.items()}


def aligned_mask(im,maxw):
    a=np.zeros((600,maxw),bool)
    off=(maxw-im.width)//2
    a[:,off:off+im.width]=np.asarray(im)[:,:,3]>=128
    return a


if __name__=='__main__':
    p=ArgumentParser()
    p.add_argument("--official",type=Path,required=True)
    p.add_argument("--before",type=Path,required=True)
    p.add_argument("--after",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--neutral-before",type=Path)
    p.add_argument("--neutral-after",type=Path)
    p.add_argument("--tails-atlas",type=Path)
    p.add_argument("--tails-before",type=Path)
    p.add_argument("--tails-after",type=Path)
    args=p.parse_args()
    images=[normalize(q) for q in (args.official,args.before,args.after)]
    names=("Official corefolder art 1","Previous VRM","Revised VRM")
    maxw=max(im.width for im in images)
    masks=[aligned_mask(im,maxw) for im in images]
    metrics={name:measure(im) for name,im in zip(names,images)}
    for name,mask in zip(names,masks):
        metrics[name]["silhouette_IoU_with_art"]=round(float((mask&masks[0]).sum()/(mask|masks[0]).sum()),4)
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"Fit-Mui.json").write_text(json.dumps(metrics,indent=2)+"\n",encoding="utf-8")
    board=Image.new("RGB",(3*(maxw+28),660),"#eeeef0")
    draw=ImageDraw.Draw(board)
    try:font=ImageFont.truetype("segoeui.ttf",24)
    except OSError:font=ImageFont.load_default()
    for j,(item,label) in enumerate(zip(images,names)):
        x=j*(maxw+28)+(maxw+28-item.width)//2
        board.paste(item,(x,48),item)
        draw.text((x,8),label,font=font,fill="#292b30")
    board.save(args.out/"Fit-Mui.png",optimize=True)
    if all((args.neutral_before,args.neutral_after,args.tails_atlas,args.tails_before,args.tails_after)):
        neutral=[images[0],normalize(args.neutral_before),normalize(args.neutral_after)]
        tails=[normalize(path) for path in (args.tails_atlas,args.tails_before,args.tails_after)]
        w=max(im.width for im in neutral+tails)
        board=Image.new("RGB",(3*(w+20),1312),"#eeeef0")
        draw=ImageDraw.Draw(board)
        report={}
        for row,(items,labels) in enumerate(((neutral,("Official pose 1","Previous neutral VRM","Revised neutral VRM")),
                (tails,("Official TailsUnit","Previous neutral tails","Revised neutral tails")))):
            masks=[aligned_mask(im,w) for im in items]
            for j,(im,name,mask) in enumerate(zip(items,labels,masks)):
                left=j*(w+20)+(w+20-im.width)//2
                board.paste(im,(left,48+row*654),im)
                draw.text((left,8+row*654),name,font=font,fill="#292b30")
                report[name]={"width_over_height":round(im.width/im.height,4),
                    "silhouette_IoU_with_art":round(float((mask&masks[0]).sum()/(mask|masks[0]).sum()),4)}
        board.save(args.out/"Fit-Mui-Neutral.png",optimize=True)
        (args.out/"Fit-Mui-Neutral.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")

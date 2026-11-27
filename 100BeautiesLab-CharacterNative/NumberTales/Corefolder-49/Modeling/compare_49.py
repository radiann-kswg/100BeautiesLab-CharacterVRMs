"""Measure the official PNGs and matching orthographic renders in object-height units."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy.ndimage import label,find_objects


def frame(image):
    a=image.getchannel('A')
    bounds=a.point(lambda x:255 if x>=128 else 0).getbbox()
    image=image.crop(bounds)
    return image.resize((round(image.width*500/image.height),500),Image.Resampling.LANCZOS)


def components(mask, min_area):
    ids,n=label(mask,np.ones((3,3)))
    out=[]
    for i,sl in enumerate(find_objects(ids),1):
        if sl is None: continue
        ys,xs=sl
        roi=ids[sl]==i
        count=int(np.count_nonzero(roi))
        if count<min_area: continue
        y,x=np.nonzero(roi)
        out.append(dict(x=xs.start,y=ys.start,w=xs.stop-xs.start,h=ys.stop-ys.start,
                        cx=round(float(x.mean())+xs.start,2),cy=round(float(y.mean())+ys.start,2),area=count))
    return sorted(out,key=lambda p:-p['area'])


def analyze(image):
    a=np.array(image,dtype=int)
    h,w=a.shape[:2]
    y,x=np.mgrid[:h,:w]
    r,g,b=np.moveaxis(a[:,:,:3],-1,0)
    opaque=a[:,:,3]>190
    def comp(m,area=4): return components(m&opaque,area)
    def paired(blobs):
        cs=sorted(blobs[:2],key=lambda p:p['cx'])
        return cs
    eye=paired(comp((y>.18*h)&(y<.32*h)&(b-r>60)&(b-g>40)&(g<146)&(r<120),10))
    pupils=paired(comp((y>.18*h)&(y<.32*h)&(r-g>22)&(b-r>19)&(r>95),2))
    mark=comp((y>h*.33)&(y<h*.57)&(x>w*.41)&(x<w*.71)&(r<108)&(b-r>7)&(g-r<19),4)
    mark=[p for p in mark if p['h']>=.016*h][:2]
    dark=(r<164)&(g<164)&(b<168)&(abs(r-b)<27)
    jaw=comp((y>h*.26)&(y<h*.41)&(x>w*.22)&(x<w*.68)&dark)
    jaw=[p for p in jaw if p['w']>3*p['h'] and p['w']>.07*h and abs(w*.48-p['cx'])<w*.19]
    mouth=[]
    if len(eye)==2:
        xc=(eye[0]['cx']+eye[1]['cx'])/2-h*.036
        yc=(eye[0]['cy']+eye[1]['cy'])/2+h*.051
        local=comp((abs(x-xc)<h*.055)&(abs(y-yc)<h*.024)&dark,2)
        mouth=sorted([p for p in local if p['w']<h*.068 and p['h']<h*.023],
                     key=lambda p:(p['cx']-xc)**2+(p['cy']-yc)**2)
    pale=(abs(r-155)<16)&(abs(g-193)<16)&(abs(b-230)<17)&(r>128)
    paws=paired(comp(pale&(y>.66*h),60))
    blush=comp((r-g>22)&(g-b>3)&(r>195)&(y<.39*h),1)
    def horizontal(yfrac,mask):
        row=round(yfrac*(h-1))
        u=np.flatnonzero(mask[row])
        return int(u[-1]-u[0]+1) if len(u) else 0
    white=(r>239)&(g>239)&(b>239)&opaque
    res=dict(size=[w,h],eyes=eye,pupils=pupils,mark=mark,jawline=jaw[:1],mouth=mouth[:1],front_tips=paws,
             cheek_stroke_pixels=sum(p['area'] for p in blush),
             silhouette_widths={str(v):horizontal(v,opaque) for v in [.05,.10,.18,.45,.65,.88]},
             bib_widths={str(v):horizontal(v,white) for v in [.54,.64,.74]})
    if len(eye)==2:
        res['eye_mid_offset']=round(((eye[0]['cx']+eye[1]['cx'])/2-w/2)/h,4)
        res['eye_separation']=round(eye[1]['cx']-eye[0]['cx'],2)
    return res


def rear_projection(path,out):
    """Parallel projection of the actual tail triangles, preserving x/y scale."""
    training=Path(__file__).resolve().parents[2]/'Corefolder-Training'
    sys.path.insert(0,str(training))
    from check_character_export import Glb
    model=Glb(path)
    triangles=[]
    for mesh in model.doc['meshes']:
        if 'tail' not in mesh.get('name','').lower():
            continue
        for primitive in mesh['primitives']:
            pos=model.array(primitive['attributes']['POSITION'])[:,:2].copy()
            pos[:,1]*=-1
            triangles.append(pos[model.array(primitive['indices']).reshape(-1,3)])
    if not triangles:raise ValueError('Missing tail geometry')
    tri=np.concatenate(triangles,axis=0)
    low,high=tri.min(axis=(0,1)),tri.max(axis=(0,1))
    scale=750/max(high-low)
    pix=(tri-low)*scale+3
    dims=np.ceil((high-low)*scale+7).astype(int)
    image=Image.new('RGBA',tuple(dims))
    draw=ImageDraw.Draw(image)
    for t in pix:
        draw.polygon([tuple(q) for q in t],fill=(106,166,215,255))
    image.save(out)


def cell(strip,slot):
    return frame(strip.crop((720*slot,0,720*(slot+1),strip.height)))


def compare(db,before,after,out,angles,yaw=None,before_vrm=None,after_vrm=None):
    root=db/'data/Works_NumberTales/Images/DB_Primary/corefolder/49'
    papers=[frame(Image.open(root/f'emstk_corefolderNTS-49-{i}.png').convert('RGBA')) for i in (1,2)]
    priors=[cell(Image.open(before),i) for i in range(len(angles))]
    canonical=[analyze(im) for im in papers]
    before_metrics=[analyze(im) for im in priors]
    # Face center relative to the outside silhouette fixes the yaw without
    # fitting away later changes to eye size, lower tails, hair or the muzzle.
    if yaw is None:
        mean=np.mean([k['eye_mid_offset'] for k in canonical])
        ix=min(range(len(angles)),key=lambda j:abs(before_metrics[j].get('eye_mid_offset',10)-mean))
    else: ix=angles.index(yaw)
    images=[*papers,priors[ix]]
    titles=['Official 1','Official 2',f'Previous VRM   {angles[ix]} deg']
    results=dict(method='Alpha >= 128 trim; height normalized to 500 px; RGB masks and 8-connected components',
                 angles=angles,selected_yaw=angles[ix],angle_eye_offsets=[k.get('eye_mid_offset') for k in before_metrics],
                 official_1=canonical[0],official_2=canonical[1],before=before_metrics[ix])
    if after:
        revised=cell(Image.open(after),ix)
        images.append(revised)
        titles.append(f'Revised VRM   {angles[ix]} deg')
        results['after']=analyze(revised)
    out.mkdir(parents=True,exist_ok=True)
    if before_vrm and after_vrm:
        with TemporaryDirectory() as temp:
            temp=Path(temp)
            rear_projection(before_vrm,temp/'before.png')
            rear_projection(after_vrm,temp/'after.png')
            from compare_corefolder_art import compare as compare_rear
            results['rear']=compare_rear(db/'data/Works_NumberTales/Images/DB_Primary/attr/tailsUnit/attr_tailsUnitNTS-49.png',
                                         temp/'before.png',temp/'after.png',out/'tail-overlap.png')
            results['before_vrm_sha256']=hashlib.sha256(before_vrm.read_bytes()).hexdigest()
            results['after_vrm_sha256']=hashlib.sha256(after_vrm.read_bytes()).hexdigest()
    (out/'projection.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    widest=max(im.width for im in images)+24
    page=Image.new('RGB',(widest*len(images),558),(230,232,235))
    draw=ImageDraw.Draw(page)
    try: font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',24)
    except OSError: font=ImageFont.load_default()
    for i,(im,title) in enumerate(zip(images,titles)):
        offset=(widest*i+(widest-im.width)//2,49)
        page.paste(im,offset,im.getchannel('A'))
        draw.text((widest*i+16,9),title,font=font,fill=(37,43,54))
    page.save(out/'artwork-comparison.png')
    print('YAW',angles[ix],results['angle_eye_offsets'])
    for tag in ['official_1','official_2','before','after']:
        if tag not in results: continue
        m=results[tag]
        print(tag,'W',m['size'][0],'eye',[(p['w'],p['h'],p['cx'],p['cy']) for p in m['eyes']],
              'mouth',[(p['w'],p['h'],p['cy']) for p in m['mouth']],
              'paw',[(p['w'],p['h'],p['cx'],p['cy']) for p in m['front_tips']],
              'headAt10',m['silhouette_widths']['0.1'],'cheek',m['cheek_stroke_pixels'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('database',type=Path);p.add_argument('before',type=Path);p.add_argument('out',type=Path)
    p.add_argument('--after',type=Path);p.add_argument('--angles',nargs='+',type=int,default=[-18,-24,-30,-36])
    p.add_argument('--yaw',type=int)
    p.add_argument('--before-vrm',type=Path);p.add_argument('--after-vrm',type=Path)
    args=p.parse_args()
    compare(args.database,args.before,args.after,args.out,args.angles,args.yaw,args.before_vrm,args.after_vrm)

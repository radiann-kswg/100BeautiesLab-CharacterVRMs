"""Trace separate plumes and their tip markings from the official rear atlas."""
from pathlib import Path
import argparse,json,math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as nd

HERE=Path(__file__).resolve().parent
# A seed in each visible plume; small connecting tufts visible between plumes are completed behind the overlap.
LANDMARKS={
 57:[((195,94),None,[(268,199),(167,105),(152,171)]),((347,95),None,[(277,199),(373,103),(391,171)]),
     ((113,201),None,[(266,205),(224,285),(139,298)]),((431,201),None,[(278,205),(322,285),(406,298)]),
     ((272,298),None,[]),((147,409),None,[(260,339),(222,280),(147,285)]),((398,409),None,[(285,340),(324,280),(396,285)])],
 85:[((263,131),None,[]),((139,151),None,[(143,80),(236,106),(250,221),(149,209)]),
     ((387,151),None,[(381,80),(292,106),(277,221),(379,209)]),
     ((69,244),None,[(200,215),(149,286),(97,305)]),((457,244),None,[(328,215),(379,286),(431,305)]),
     ((171,317),None,[]),((355,318),None,[]),((262,435),(262,367),[(166,385),(263,332),(363,383),(346,449),(198,449)])]}
PALETTES={57:((255,238,98),(247,255,185)),85:((196,132,85),(239,157,70))}

def contour_region(mask,ctr):
    cy,cx=ctr[1],ctr[0]
    y,x=np.nonzero(mask)
    radius=np.hypot(x-cx,y-cy)
    theta=np.arctan2(y-cy,x-cx)%(2*np.pi)
    bins=720
    index=np.floor(theta*bins/(2*np.pi)).astype(int)%bins
    edge=np.zeros(bins)
    np.maximum.at(edge,index,radius)
    valid=np.flatnonzero(edge)
    edge=np.interp(np.arange(bins),valid,edge[valid],period=bins)
    # The original locates each lobe and its tips. Smooth small variations in
    # the brush outline before constructing the broad curved VRM surfaces.
    edge=nd.gaussian_filter1d(nd.median_filter(edge,3,mode='wrap'),1.8,mode='wrap')
    angles=(np.arange(bins)+.5)*2*np.pi/bins
    points=np.column_stack((cx+edge*np.cos(angles),cy+edge*np.sin(angles)))
    # Keep the actual pointed tips and indentations as well as enough points on long curves.
    chosen={0,180,360,540,719}
    def refine(a,b):
        chord=points[b]-points[a]; t=np.arange(a,b+1)
        normal=abs(chord[0]*(points[t,1]-points[a,1])-chord[1]*(points[t,0]-points[a,0]))/max(np.linalg.norm(chord),1)
        k=a+int(normal.argmax())
        if normal.max()<=2.1 and np.linalg.norm(chord)<29:return
        if k<=a or k>=b:k=(a+b)//2
        if a<k<b:chosen.add(k);refine(a,k);refine(k,b)
    for a,b in zip(sorted(chosen)[:-1],sorted(chosen)[1:]):refine(a,b)
    return points[sorted(chosen)]

def fur_colors(pixels, mask, base, tip):
    """Fit a broad, curved tip marking and carry it smoothly around the volume."""
    colors=pixels[:,:,:3].astype(float)
    a=mask & (np.linalg.norm(colors-base,axis=2)<6)
    b=mask & (np.linalg.norm(colors-tip,axis=2)<6)
    if min(a.sum(),b.sum())<12:
        raise ValueError("Both fur colors must be visible on every plume")
    grid=np.indices(mask.shape).transpose(1,2,0)
    origin=grid[a].mean(axis=0)
    axis=grid[b].mean(axis=0)-origin
    axis/=np.linalg.norm(axis)
    across=np.array([-axis[1],axis[0]])
    reach=(grid-origin)@axis
    cross=(grid-origin)@across
    da=nd.distance_transform_edt(~a)
    db=nd.distance_transform_edt(~b)
    seam=(da+db<5)&(np.abs(da-db)<=1.5)
    if np.count_nonzero(seam)<6:
        raise ValueError("Insufficient visible boundary between fur and tip")
    x,y=cross[seam],reach[seam]
    # Cap extrapolation at the slope measured at the last visible boundary.
    # Nearest-pixel filling casts sawtooth streaks along the previously hidden
    # side surface when a viewer rotates the model away from the back.
    poly=np.polynomial.Polynomial.fit(x,y,2)
    lo,hi=np.quantile(x,[.025,.975])
    sample=np.clip(cross,lo,hi)
    boundary=poly(sample)+(cross-sample)*np.clip(poly.deriv()(sample),-1.,1.)
    fraction=np.clip(.5+reach-boundary,0,1)
    return np.uint8(np.rint(base+fraction[:,:,None]*(tip-base)))

def bake(n,db,dest):
    f=db/f'data/Works_NumberTales/Images/DB_Primary/attr/tailsUnit/attr_tailsUnitNTS-{n}.png'
    pixels=np.asarray(Image.open(f).convert('RGBA'));h,w=pixels.shape[:2]
    labels,_=nd.label((pixels[:,:,3]>120)&(pixels[:,:,:3].max(2)>130))
    dst=Image.new('RGB',(1024,1024),PALETTES[n][0])
    result=[]
    for i,(seed,extra,occluded) in enumerate(LANDMARKS[n]):
        mask=labels==labels[seed[1],seed[0]]
        if extra:mask|=labels==labels[extra[1],extra[0]]
        sup=Image.fromarray(mask);d=ImageDraw.Draw(sup)
        if occluded:d.polygon(occluded,fill=1)
        if n==57 and i in (0,1):
            # A short yellow root is visible above the central tail. Let the two upper
            # plumes meet behind it and below the central lobe, as seen in the atlas.
            points=[(190,103),(263,168),(276,207),(284,232),(229,254),(202,215)]
            d.polygon(points if i==0 else [(w-x,y) for x,y in points],fill=1)
        full=nd.binary_fill_holes(nd.binary_closing(np.asarray(sup),iterations=2))
        full=nd.binary_dilation(full,iterations=2)
        ctr=seed
        points=contour_region(full,ctr)
        base,tip=np.array(PALETTES[n],float)
        image=fur_colors(pixels,mask,base,tip)
        x0,y0=np.floor(points.min(0)-3).astype(int); x1,y1=np.ceil(points.max(0)+4).astype(int)
        tile=Image.fromarray(image).crop((x0,y0,x1,y1)).resize((252,252),Image.Resampling.LANCZOS)
        tx=(i%4)*256+2;ty=(i//4)*256+2
        dst.paste(tile,(tx,ty))
        result.append(dict(center=ctr,outline=np.round(points,2).tolist(),crop=[int(x0),int(y0),int(x1),int(y1)],tile=[tx,ty]))
    dest.mkdir(parents=True,exist_ok=True);dst.save(dest/f'Tails-{n}.png')
    (dest/f'Tails-{n}.json').write_text(json.dumps(dict(size=[w,h],plumes=result),separators=(',',':')))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',type=Path,required=True);p.add_argument('numbers',nargs='+',type=int,choices=(57,85));a=p.parse_args()
    for n in a.numbers:bake(n,a.db,HERE.parent/f'Corefolder-{n}/Modeling')

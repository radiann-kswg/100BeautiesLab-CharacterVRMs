"""Intersect real VRMs and their base-color textures at fixed torso heights in both views."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE.parents[1]/'Corefolder-Training'))
from check_character_export import Glb,sha


def inspect(path):
    glb=Glb(path)
    doc=glb.doc
    images={}
    parts=[]
    for node in doc['nodes']:
        if 'mesh' not in node:continue
        group=node.get('name','').lower().split('.')[0]
        for prim in doc['meshes'][node['mesh']]['primitives']:
            pos=glb.array(prim['attributes']['POSITION'])
            faces=glb.array(prim['indices']).reshape(-1,3)
            uv=glb.array(prim['attributes']['TEXCOORD_0']) if 'TEXCOORD_0' in prim['attributes'] else np.zeros((len(pos),2))
            mat=doc['materials'][prim['material']]
            pbr=mat.get('pbrMetallicRoughness',{})
            image=None
            if (texture:=pbr.get('baseColorTexture')) is not None:
                source=doc['textures'][texture['index']]['source']
                if source not in images:
                    data=glb.buffer(doc['images'][source]['bufferView'])
                    images[source]=np.asarray(Image.open(BytesIO(data)).convert('RGBA'))
                image=images[source]
            factor=np.array(pbr.get('baseColorFactor',[1,1,1,1]))[:3]
            parts.append((group,np.column_stack((-pos[:,0],pos[:,2],pos[:,1],uv))[faces],image,factor))
    result={}
    rays=np.arange(-.74975,.750,.0005)
    for z in (.045,.10,.18,.28,.36,.48,.57,.64):
        heights={}
        for view,axis in [('front',0),('side',1)]:
            depth=[np.full(rays.size,np.inf),np.full(rays.size,np.inf)]
            white=[np.zeros(rays.size,bool),np.zeros(rays.size,bool)]
            seen=np.full(rays.size,'',dtype='U12')
            for group,tris,im,factor in parts:
                selected=tris[(tris[:,:,2].min(1)<=z)&(tris[:,:,2].max(1)>z)]
                for triangle in selected:
                    other=np.roll(triangle,1,axis=0)
                    hit=(triangle[:,2]>z)!=(other[:,2]>z)
                    a,b=triangle[hit],other[hit]
                    p,q=a+(b-a)*((z-a[:,2])/(b[:,2]-a[:,2]))[:,None]
                    left,right=sorted([p[axis],q[axis]])
                    ix=np.arange(*np.searchsorted(rays,[left,right]))
                    if not len(ix):continue
                    mix=(rays[ix]-p[axis])/(q[axis]-p[axis])
                    sample=p+(q-p)*mix[:,None]
                    c=np.tile(np.r_[255*factor**(1/2.2),255],(len(ix),1))
                    if im is not None:
                        h,w=im.shape[:2]
                        sx=(sample[:,3]*w).astype(int)%w;sy=(sample[:,4]*h).astype(int)%h
                        c*=im[sy,sx]/255
                    for j in ([0,1] if group=='body' else [1]):
                        valid=(sample[:,1-axis]<depth[j][ix])&(c[:,3]>127)
                        ii=ix[valid];rgb=c[valid,:3]
                        depth[j][ii]=sample[valid,1-axis]
                        white[j][ii]=(rgb.min(1)>228)&(np.ptp(rgb,axis=1)<20)
                        if j:seen[ii]=group
            shell=np.isfinite(depth[0])
            visible=(seen=='body')&shell
            total=shell.sum()
            span_mm=lambda mask:round(float(mask.sum()*.5),1)
            heights[view]={'shell_mm':span_mm(shell),'visible_mm':span_mm(visible),
                           'white_mm':span_mm(white[0]&shell),'visible_white_mm':span_mm(white[1]&visible),
                           'tail_over_body_mm':span_mm((seen=='tail')&shell),
                           'visible_fraction':round(visible.sum()/max(1,total),3)}
        result[str(z)]=heights
    return {'sha256':sha(glb.data),'sections_m':result}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('out',type=Path)
    p.add_argument('--numbers',type=int,nargs='+',default=[4,16,20,22,25,93,49,85])
    p.add_argument('--candidate',type=Path)
    args=p.parse_args()
    data={}
    for n in args.numbers:
        if n in (49,85):
            folder=args.candidate/str(n) if args.candidate else HERE.parents[1]/f'Corefolder-{n}/Modeling'
            path=folder/f'Corefolder-{n}.vrm'
        else:
            path,=(ROOT/f'Assets/100BeautiesLab-CharacterVRM/NumberTales/Corefolder-{n}').glob('*.vrm')
        data[str(n)]=inspect(path)
    args.out.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')

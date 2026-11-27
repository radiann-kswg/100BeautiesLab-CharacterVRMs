"""Measure the unclothed body from actual Blender surfaces at common world-space heights."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

HERE=Path(__file__).resolve().parent
NATIVE=HERE.parents[2]


def measure(source,name):
    import bpy
    bpy.ops.wm.open_mainfile(filepath=str(source.resolve()),use_scripts=False)
    obj=bpy.data.objects[name]
    if name=='body':
        sub=obj.modifiers.new('Evaluated source curvature','SUBSURF')
        sub.levels=2
        obj=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    verts=np.asarray([obj.matrix_world@v.co for v in obj.data.vertices],dtype=float)
    edges=np.array([e.vertices[:] for e in obj.data.edges])
    # Weld only for graph traversal; duplicated UV vertices must not split the
    # main torso, and detached collar or marking islands must not widen a section.
    _,ix=np.unique(np.round(verts,5),axis=0,return_inverse=True)
    graph=[set() for _ in range(ix.max()+1)]
    for a,b in ix[edges]:
        graph[a].add(b); graph[b].add(a)
    seed=ix[np.argmin(verts[:,2])]
    seen={seed}; todo=[seed]
    while todo:
        new=graph[todo.pop()]-seen
        seen.update(new);todo.extend(new)
    ids=np.isin(ix,list(seen))
    full=verts[ids];edges=edges[ids[edges[:,0]]]
    a,b=verts[edges[:,0]],verts[edges[:,1]]
    ground=full[:,2].min()
    heights=[.01,.025,.05,.10,.15,.20,.30,.40,.50,.57,.60,.64,.67,.69,.70,.71]
    sections={}
    for h in heights:
        z=ground+h
        sel=(a[:,2]<=z)!=(b[:,2]<=z)
        if not sel.any():continue
        p,q=a[sel],b[sel]
        cut=p+(q-p)*((z-p[:,2])/(q[:,2]-p[:,2]))[:,None]
        lo,hi=cut.min(0),cut.max(0)
        sections[str(h)]={'width_mm':round((hi[0]-lo[0])*1000,2),
                          'depth_mm':round((hi[1]-lo[1])*1000,2),
                          'front_y_mm':round(lo[1]*1000,2),'back_y_mm':round(hi[1]*1000,2)}
    return {'dimensions_mm':(np.ptp(full,axis=0)*1000).round(2).tolist(),
            'ground_z_mm':round(ground*1000,2),'sections':sections}


def review(number,before,after,old_tile,new_tile,clay,output):
    from PIL import Image,ImageDraw,ImageFont
    past=json.loads(before.read_text(encoding='utf8'))
    now=json.loads(after.read_text(encoding='utf8'))
    out={'method':'Unclothed native body, ground-relative plane sections in Blender world coordinates. Millimetres.',
         'basis':now['Basis'],'ref25':now['25'],'ref93':now['93'],'before':past[str(number)],'after':now[str(number)]}
    for label,p in [('before',old_tile),('after',new_tile)]:
        out[label]['vrm_sha256']=json.loads(p.with_suffix('.json').read_text(encoding='utf8'))['sha256']
    output.mkdir(parents=True,exist_ok=True)
    (output/'body-sections.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
    entries=[('Common basis',clay/'Base.png'),('Reference #25',clay/'25.png'),('Reference #93',clay/'93.png'),
             (f'Previous #{number}',old_tile),(f'Revised #{number}',new_tile)]
    width=255
    canvas=Image.new('RGB',(width*len(entries),577),'#e9eaed')
    draw=ImageDraw.Draw(canvas)
    font=ImageFont.truetype('segoeui.ttf',20)
    small=ImageFont.truetype('segoeui.ttf',14)
    for i,(title,file) in enumerate(entries):
        board=Image.open(file)
        cell=board.width//3
        draw.text((i*width+7,7),title,font=font,fill='#262c35')
        # Identical camera/ortho-scale. Compare the whole side to the
        # unclothed front, which separates the body from silhouette-making tails.
        for row,(col,y,title) in enumerate(((1,0,'Whole model, side'),(0,1,'Body group, front'))):
            crop=board.crop((col*cell,y*cell,(col+1)*cell,(y+1)*cell)).resize((width-2,width-2),Image.Resampling.LANCZOS)
            h=35+row*270
            canvas.paste(crop,(i*width+1,h))
            if not i:draw.text((7,h+width-23),title,font=small,fill='white')
    canvas.save(output/'structure-comparison.png')


if __name__=='__main__':
    if '--sheet' in sys.argv:
        p=argparse.ArgumentParser(description='Compare previously measured bodies and same-camera clay tiles.')
        p.add_argument('number',type=int)
        for name in ('before','after','old_tile','new_tile','clay','out'):
            p.add_argument(name,type=Path)
        a=p.parse_args(sys.argv[sys.argv.index('--sheet')+1:])
        review(a.number,a.before,a.after,a.old_tile,a.new_tile,a.clay,a.out)
        raise SystemExit
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out',type=Path)
    parser.add_argument('--numbers',type=int,nargs='+',default=[49,85])
    parser.add_argument('--candidate',type=Path,help='Directory containing numbered subdirectories of candidate blends')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    files={'Basis':(NATIVE/'Basis/Corefolder/VRCModel_CoreFloder-Base.blend','body'),
           '25':(NATIVE/'NumberTales/Corefolder-25/VRCModel_CoreFloder-25.blend','Body.002'),
           '93':(NATIVE/'NumberTales/Corefolder-93/VRCModel_CoreFloder-93.blend','Body')}
    for n in args.numbers:
        folder=args.candidate/str(n) if args.candidate else NATIVE/'NumberTales'/f'Corefolder-{n}'/'Modeling'
        files[str(n)]=(folder/f'Corefolder-{n}.blend','Body')
    data={key:measure(path,obj) for key,(path,obj) in files.items()}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
    for key,v in data.items():
        print('TORSO',key,v['dimensions_mm'],v['sections'].get('0.05'),v['sections'].get('0.64'))

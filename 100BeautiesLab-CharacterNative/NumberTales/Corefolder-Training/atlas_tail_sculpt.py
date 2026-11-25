"""Build independently skinned, rounded volumes from the measured rear plume contours."""
import json, math
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from refine_models import toon

HERE=Path(__file__).resolve().parent
# Distances in metres from the common torso. Layering follows the overlap in each rear drawing.
LAYERS={57:[.017,.017,.036,.036,.130,.072,.072],85:[.063,.014,.014,-.010,-.010,.102,.102,.034]}
TIPS={57:[(163,9),(382,9),(18,122),(527,125),(211,169),(31,443),(515,443)],
      85:[(263,6),(107,58),(422,56),(11,256),(518,254),(63,370),(466,367),(262,490)]}

def revise_tails(n,arm,collection):
    folder=HERE.parent/f'Corefolder-{n}/Modeling'
    data=json.loads((folder/f'Tails-{n}.json').read_text())
    w,h=data['size']
    tex=bpy.data.images.load(str(folder/f'Tails-{n}.png'),check_existing=False);tex.pack()
    mat=toon(f'{n} • fox-tail rear atlas','#FFFFFF',.0022)
    m=mat.vrm_addon_extension.mtoon1
    m.pbr_metallic_roughness.base_color_texture.index.source=tex
    m.pbr_metallic_roughness.base_color_factor=(.765,.765,.765,1)
    t=m.extensions.vrmc_materials_mtoon
    t.shade_multiply_texture.index.source=tex
    t.shade_color_factor=(.80,.78,.74)
    t.shading_shift_factor=.12
    count=5 if n==57 else 3
    # Preserve the measured aspect of the rear atlas. The tall central plumes sit behind the head.
    span=1.215 if n==57 else 1.22
    top=.014+span*(h-12)/(w-12)
    guide={}
    for i,record in enumerate(data['plumes']):
        name=f'Tail_{"Upper" if i<count else "Lower"}_{i+1:02}'
        obj=collection.objects.get(name)
        if obj is None:raise ValueError(f'Missing source tail {name}')
        uvpoints=[];verts=[];faces=[]
        center=Vector(record['center']); edge=[Vector(p) for p in record['outline']]
        crop=record['crop']; tile=record['tile'];num=len(edge)
        def point(p,bend=0):
            x=(p.x-w/2)*span/(w-12)
            z=.014+(1-(p.y-6)/(h-12))*(top-.014)
            y=.367-.37*(abs(x)/(.5*span))**1.7+LAYERS[n][i]-.035*(1-z/top)
            if n==85 and i in (5,6):
                # The full-body art shows the orange lower pair curling down
                # around the flanks. Keep their shared rump and bend the bulbs.
                reach=bend*min(1,max(0,(abs(x)-.08)/.32))*min(1,max(0,(.68-z)/.36))
                sign=1 if x>=0 else -1
                x+=.158*sign*reach
                z-=min(max(0,z-.022),.215*reach)
                y-=.29*reach
            return Vector((x,y,z))
        side=1 if center.x>w/2+18 else -1 if center.x<w/2-18 else 0
        root=Vector((side*.075,.264,.36 if i<count else .27))
        def vertex(p,offset=0,attachment=0,bend=0):
            pos=point(p,bend);pos.y+=offset
            if attachment:pos=pos.lerp(root,attachment)
            verts.append(tuple(pos))
            uvpoints.append(((tile[0]+.5+(p.x-crop[0])/(crop[2]-crop[0])*251)/1024,
                             1-(tile[1]+.5+(p.y-crop[1])/(crop[3]-crop[1])*251)/1024))
            return len(verts)-1
        front=vertex(center,-.115,1)
        rings=[]
        # Smooth sections across the entire width; both caps share the outermost ring.
        for angle in (15,35,55,73,90,107,125,145,165):
            phase=math.radians(angle); r=math.sin(phase)
            offset=-math.cos(phase)*(.145 if angle<90 else .128)
            attachment=max(0,math.cos(phase))**3*.90
            # Only the outward flank sweeps toward the belly. The rear surface
            # still fills the eight-lobe cluster seen square-on in the atlas.
            bend=math.sin(math.pi*min(1,angle/117))**.65 if angle<117 else 0
            ring=[vertex(center.lerp(p,r),offset,attachment,bend) for p in edge]
            rings.append(ring)
        back=vertex(center,.128)
        for j in range(num):
            k=(j+1)%num
            faces.append((front,rings[0][k],rings[0][j]))
            for a,b in zip(rings,rings[1:]):faces.append((a[j],a[k],b[k],b[j]))
            faces.append((rings[-1][j],rings[-1][k],back))
        mesh=bpy.data.meshes.new(name+' • rounded atlas geometry')
        mesh.from_pydata(verts,[],faces); mesh.update();mesh.materials.append(mat)
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        uv=mesh.uv_layers.new(name='Local plume atlas')
        for poly in mesh.polygons:
            poly.use_smooth=True
            for li in poly.loop_indices:uv.data[li].uv=uvpoints[mesh.loops[li].vertex_index]
        obj.data=mesh
        bulb=point(center); bulb.y+=.014
        tip=point(Vector(TIPS[n][i]),.7)
        # Guide follows the route around the flank, ending on the visible tip.
        guide[name]=[tuple(root),tuple(root.lerp(bulb,.55)),tuple(bulb),tuple(bulb.lerp(tip,.60)),tuple(tip)]
    return guide

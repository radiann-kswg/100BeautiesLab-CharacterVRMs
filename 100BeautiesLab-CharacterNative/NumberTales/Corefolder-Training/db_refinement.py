"""DB-specific sculpting. Contour coordinates are traced from the official tail diagrams,
then given thickness; they are modeling interpretations, not newly authored canon.
"""
from pathlib import Path
import math,json
import bpy,bmesh,numpy as np
from mathutils import Vector
from modeling_draft import mesh_object,bind,lock,sha,bezier
DB=Path(r'D:/VisualStudio Code Userfile/100BeautiesLab_CreationsDB/data/Works_NumberTales')
IMAGES=DB/'Images/DB_Primary'

def contour_volume(name,outline,center,depth,mats,collection):
    # Periodic Catmull-Rom sampling keeps the drawn forked tips in a closed, rounded mesh.
    pts=[Vector(p) for p in outline];edge=[]
    for i,p1 in enumerate(pts):
        p0=pts[i-1];p2=pts[(i+1)%len(pts)];p3=pts[(i+2)%len(pts)]
        for k in range(3):
            t=k/3;edge.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t))
    c=Vector(center);verts=[];faces=[];sides=len(edge);radii=(.20,.45,.68,.86,1)
    # Shared silhouette ring joins front and rear surfaces without duplicate vertices.
    for sign in (-1,1):
        start=len(verts);verts.append(tuple(c+Vector((0,sign*depth,0))))
        for r in radii[:-1] if sign==1 else radii:
            for p in edge:verts.append(tuple(c+(p-c)*r+Vector((0,sign*depth*math.sqrt(1-r*r),0))))
        for j in range(sides):faces.append((start,start+1+j,start+1+(j+1)%sides))
        for ring in range(3):
            a=start+1+ring*sides;b=a+sides
            for j in range(sides):faces.append((a+j,b+j,b+(j+1)%sides,a+(j+1)%sides))
        a=start+1+3*sides;b=1+4*sides
        for j in range(sides):faces.append((a+j,b+j,b+(j+1)%sides,a+(j+1)%sides))
    obj=mesh_object(name,verts,faces,mats,collection)
    bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
    return obj

# Coordinates use a 390 x 390 reading grid of the original diagrams; no generated sheet is traced.
TOP57=[(195,178),(190,110),(167,73),(150,65),(142,33),(122,48),(133,72),(114,52),(109,30),(86,59),(74,88),(75,112),(114,124),(155,148)]
SIDE57=[(195,175),(155,139),(123,122),(88,115),(64,113),(45,93),(46,137),(26,133),(9,113),(5,150),(9,194),(27,231),(59,251),(106,252),(154,226)]
LOW57=[(191,302),(168,255),(133,232),(94,223),(65,225),(49,241),(44,270),(50,303),(58,320),(38,335),(24,339),(39,362),(66,377),(104,382),(140,374),(173,350)]
MID57=[(195,187),(171,181),(150,149),(134,176),(121,214),(119,253),(132,290),(155,308),(196,315),(234,307),(261,286),(269,252),(265,215),(251,174),(236,149),(218,180)]
TOP85=[(195,32),(181,58),(154,80),(143,113),(145,145),(162,174),(192,188),(227,177),(249,147),(253,117),(242,87),(208,54)]
UP85=[(158,81),(123,77),(104,82),(90,94),(77,89),(70,68),(55,94),(44,127),(49,166),(68,195),(98,207),(126,186),(148,174),(141,126)]
SIDE85=[(94,180),(68,175),(55,155),(43,145),(35,153),(24,145),(22,175),(20,199),(32,220),(18,215),(8,209),(11,239),(32,263),(58,276),(93,266),(115,236)]
LOW85=[(194,191),(165,183),(131,187),(103,202),(83,223),(79,254),(57,255),(70,275),(47,282),(70,302),(65,311),(50,309),(73,325),(112,335),(152,325),(178,304),(188,276),(194,239)]
MID85=[(195,291),(174,317),(150,329),(118,333),(132,355),(162,376),(195,389),(229,377),(261,357),(275,331),(245,328),(218,313)]

def db_tails(n,hair,tip,collection):
    mirror=lambda points:[(390-x,z) for x,z in points]
    # outline, center in drawing, depth layer, bone root, bone tip, tip region
    entries=([(TOP57,(128,110),.59,(190,177),(126,44),'top'),(mirror(TOP57),(262,110),.59,(200,177),(264,44),'top'),
        (SIDE57,(93,187),.65,(189,185),(37,130),'left'),(mirror(SIDE57),(297,187),.65,(201,185),(353,130),'right'),
        (MID57,(195,252),.88,(195,298),(195,181),'mid'),(LOW57,(113,311),.62,(183,280),(48,357),'lowleft'),(mirror(LOW57),(277,311),.62,(207,280),(342,357),'lowright')]
       if n==57 else [(TOP85,(197,121),.72,(195,184),(195,47),'top'),(UP85,(99,140),.60,(154,188),(73,79),'upleft'),(mirror(UP85),(291,140),.60,(236,188),(317,79),'upright'),
        (SIDE85,(58,218),.52,(105,246),(34,171),'left'),(mirror(SIDE85),(332,218),.52,(285,246),(356,171),'right'),
        (LOW85,(133,258),.82,(184,205),(82,313),'lowleft'),(mirror(LOW85),(257,258),.82,(206,205),(308,313),'lowright'),(MID85,(195,346),.57,(195,300),(195,380),'bottom')])
    specs=[];upper=5 if n==57 else 3
    for i,(outline,center,y,root,end,zone) in enumerate(entries):
        coord=lambda p:Vector(((p[0]-195)*.0031,y,1.11-(p[1]-30)*.0031))
        name=f'Tail_{"Upper" if i<upper else "Lower"}_{i+1:02}'
        tail=contour_volume(name,[coord(p) for p in outline],coord(center),.14 if n==57 else .145,[hair,tip],collection)
        # Carry the front surface into the body; rear silhouette stays faithful to the diagram.
        attachment=Vector((0,.29,.43 if i<upper else .24))
        side_count=len(outline)*3
        front_center=tail.data.vertices[0];front_center.co=attachment
        for ring,r in enumerate((.20,.45,.68,.86)):
            for j in range(side_count):
                v=tail.data.vertices[1+ring*side_count+j]
                influence=(1-r)**1.25
                v.co+=influence*(attachment-(coord(center)+Vector((0,-(.14 if n==57 else .145),0))))
        # Cut material boundaries into the topology instead of painting whole coarse quads.
        a,b,c=0,1,-(93 if n==57 else 87)
        if zone=='mid':c=-224
        elif zone in ('left','right'):a,b,c=1,0,-(86 if zone=='left' else 304)
        elif zone in ('upleft','upright'):a,b,c=1,0,-(103 if zone=='upleft' else 287)
        elif zone=='lowleft':a,b,c=-.35,1,-(315 if n==57 else 287)+38.5
        elif zone=='lowright':a,b,c=.35,1,-(315 if n==57 else 287)-98
        elif zone=='bottom':c=-340
        normal=Vector((a/.0031,0,-b/.0031));constant=a*195+b*(1.11/.0031+30)+c
        plane=-normal*constant/normal.length_squared
        bm=bmesh.new();bm.from_mesh(tail.data)
        bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-6,plane_co=plane,plane_no=normal.normalized(),clear_inner=False,clear_outer=False)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(tail.data);bm.free();tail.data.update()
        for p in tail.data.polygons:
            x,yy,z=np.mean([tail.data.vertices[v].co[:] for v in p.vertices],axis=0);px=x/.0031+195;py=(1.11-z)/.0031+30
            colored=py<(93 if n==57 else 87)
            if zone=='mid':colored=py<224
            elif zone in ('left','right'):colored=(px<86 if zone=='left' else px>304)
            elif zone in ('upleft','upright'):colored=(px<103 if zone=='upleft' else px>287)
            elif zone in ('lowleft','lowright'):colored=py>(315 if n==57 else 287)+(px-110 if zone=='lowleft' else 280-px)*.35
            elif zone=='bottom':colored=py>340
            p.material_index=int(colored)
        start=attachment;finish=coord(end);axis=finish-start
        params=[min(1,max(0,(v.co-start).dot(axis)/axis.length_squared)) for v in tail.data.vertices]
        path=[start,start.lerp(finish,1/3),start.lerp(finish,2/3),finish]
        tail['official_branch']='upper' if i<upper else 'lower';tail['shape_source']=f'attr_tailsUnitNTS-{n}.png'
        specs.append((tail,path,name,params))
    return specs

def db_face(face,n):
    # Compress the existing eye aperture and all corresponding expression deltas.
    # Fixed masks from Basis keep blink/viseme correspondence and the original UV topology.
    basis=face.data.shape_keys.key_blocks['Basis'];strength=.24 if n==57 else .45
    def ramp(v,a,b):return max(0,min(1,(v-a)/(b-a)))
    for vi,v in enumerate(basis.data):
        x,y,z=v.co;mask=ramp(abs(x),.025,.055)*ramp(.225-abs(x),0,.035)*ramp(z,.748,.765)*ramp(.91-z,0,.035)
        if y>-.24:mask=0
        scale=1-strength*mask
        for key in face.data.shape_keys.key_blocks:
            key.data[vi].co.z=.767+(key.data[vi].co.z-.767)*scale
    face['neutral_eye_source']=f'emstk_corefolderNTS-{n}-2.png; aperture compression {strength}'

def db_details(n,arm,face,hair,white,collection,toon):
    db_face(face,n)
    # Side ponytail is on the character's right (viewer left) in both DB drawings.
    old=bpy.data.objects.get('Hair ponytail')
    if old:bpy.data.objects.remove(old,do_unlink=True)
    path=([(-.18,.05,1.015),(-.45,.015,1.045),(-.52,-.025,.89),(-.45,-.12,.67)] if n==57 else
          [(-.19,.04,1.035),(-.40,.11,1.05),(-.45,.045,.91),(-.37,-.04,.78)])
    bind(lock('Hair ponytail',path,.095 if n==57 else .075,.055,[hair],collection),arm)
    bind(lock('Hair ponytail fork',[path[1],(-.46,.055,.99),(-.55,.02,.90),(-.515,-.035,.875)],.037,.025,[hair],collection),arm)
    if n==85:
        bind(lock('Hair crown swept point',[(.005,.02,1.02),(-.05,.015,1.10),(.02,-.005,1.215),(.035,-.03,1.29)],.125,.07,[hair],collection),arm)
        for obj in collection.objects:
            if obj.name.startswith('Fox ear'):
                side='R' if 'R' in obj.name.split() else 'L'
                for v in obj.data.vertices:
                    dz=max(0,v.co.z-1)
                    if side=='R':v.co.x+=dz*.48
                    else:v.co.x+=dz*.30;v.co.z=1+dz*.40
            if obj.name.startswith('Necklace'):
                obj.data.materials.clear();obj.data.materials.append(toon('85 DB pale necklace cord','#EEEEEE',0))
        gem=bpy.data.objects['Teardrop pendant'];gem.data.materials.clear();gem.data.materials.append(toon('85 DB cyan pendant','#00BACB',.0008))
        bind(lock('Pendant inset highlight',[(.005,-.490,.507),(-.008,-.491,.516),(-.011,-.484,.534),(-.004,-.473,.551)],.009,.002,[toon('85 pendant highlight','#85E6EA',0)],collection),arm,'chest')
    else:
        for name in ('57 right shoulder armband','57 armband number'):
            bpy.data.objects.remove(bpy.data.objects[name],do_unlink=True)
        mark=bpy.data.images.load(str(IMAGES/'attr/numberMark/attr_numberMarkNTS-57.png'),check_existing=False);mark.pack()
        ink=toon('57 DB number artwork','#FFFFFF',0);m=ink.vrm_addon_extension.mtoon1;m.alpha_mode='MASK';m.alpha_cutoff=.5
        m.pbr_metallic_roughness.base_color_texture.index.source=mark;m.extensions.vrmc_materials_mtoon.shade_multiply_texture.index.source=mark;m.extensions.vrmc_materials_mtoon.shading_shift_factor=1
        def point(u,v,offset=0):
            # The badge hangs vertically over the curved shoulder; it is not stretched onto the sphere.
            a=-.97+.62*u;z=.61-.05*(u-.5)+.15*(v-.5);r=.474+offset
            return (r*math.sin(a),-r*math.cos(a),z)
        for name,material,u0,u1,v0,v1,off in [('57 right shoulder armband',toon('57 white armband cloth','#FFFFFF',.001),0,1,0,1,0),('57 armband number',ink,.28,.77,.12,.88,.002)]:
            verts=[point(u0+(u1-u0)*i/12,v,off) for v in (v0,v1) for i in range(13)]
            obj=mesh_object(name,verts,[(i,i+1,14+i,13+i) for i in range(12)],[material],collection)
            uv=obj.data.uv_layers.new(name='UVMap')
            for poly in obj.data.polygons:
                for li in poly.loop_indices:
                    vi=obj.data.loops[li].vertex_index;uv.data[li].uv=(vi%13/12,vi//13)
            bind(obj,arm,'chest')
        border=toon('57 DB armband green piping','#A6BC40',0)
        for i,v in enumerate((.055,.945)):
            p=[point(u,v,.001) for u in (0,1/3,2/3,1)]
            bind(lock(f'57 armband piping {i}',p,.002,.002,[border],collection),arm,'chest')
        for i,u in enumerate((.18,.82)):
            p=[point(u,v,.004) for v in (.93,.97,1.04,1.08)]
            bind(lock(f'57 armband pin {i}',p,.004,.004,[toon(f'57 pin {i}','#DFE2CD',.0002)],collection),arm,'chest')
    paths=[IMAGES/f'corefolder/{n}/emstk_corefolderNTS-{n}-{i}.png' for i in (1,2)]+[IMAGES/f'attr/tailsUnit/attr_tailsUnitNTS-{n}.png',DB/'DataBases/db_Primary.json']
    if n==57:paths.append(IMAGES/'attr/numberMark/attr_numberMarkNTS-57.png')
    return [{'path':str(p),'sha256':sha(p)} for p in paths]

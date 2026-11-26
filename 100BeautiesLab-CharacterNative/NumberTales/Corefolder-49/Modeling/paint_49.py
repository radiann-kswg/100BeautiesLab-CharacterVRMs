"""Bake Yochika's editable UV maps from the official mark and the starter face UV layout."""
import argparse
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


HERE = Path(__file__).resolve().parent
NATIVE = HERE.parents[1]
BLUE = (106, 166, 215)
LIGHT = (155, 193, 230)

def crown_paint(base_color, shade_color, strands, destination):
    """Paint tapered breaks between locks in the azimuth/hem UV of the scalp."""
    size=768
    yy,xx=np.mgrid[:size,:size]
    theta=(xx/(size-1)-.5)*np.pi*2
    t=yy/(size-1)
    ink=np.zeros_like(theta)
    for start,end,begin,finish,curve in strands:
        v=np.clip((t-begin)/(finish-begin),0,1)
        mid=start+(end-start)*v+curve*np.sin(np.pi*v)
        width=.017*np.sin(np.pi*v)**.72
        a=np.clip((width-np.abs(theta-mid)+.005)/.01,0,1)
        ink=np.maximum(ink,a*((t>begin)&(t<finish)))
    rgb=np.array(base_color)+(np.array(shade_color)-np.array(base_color))*ink[:,:,None]
    Image.fromarray(np.rint(rgb).astype(np.uint8),'RGB').save(destination)


def reference_cheeks(face, fur, margin):
    """Transfer the reference face-flank transition, airbrushed cheek and small reflected spot."""
    w,h=203,274
    native=Image.open(NATIVE/'Corefolder-4/CoreFolder-4.png').convert('RGB').crop((0,0,w,h))
    yy,xx=np.mgrid[:h,:w]
    # White/fur boundary sampled on the native #25 face UV. Interpolate
    # through the blush, which overlays the lateral coat in that reference.
    boundary=np.interp(yy,[0,40,70,90,110,130,150,170,190,210,230,250,270],
                       [114,114,111,107,102,99,101,103,105,107,110,116,135])+margin
    blend=np.clip((xx-boundary+.8)/1.6,0,1)
    layer=255+blend[:,:,None]*(np.array(fur,dtype=float)-255)
    sample_x=np.clip(np.rint((xx-104)*1.18+96).astype(int),0,w-1)
    source=np.asarray(native,dtype=float)[yy,sample_x,1]
    soft=np.asarray(native.filter(ImageFilter.GaussianBlur(3)),dtype=float)[yy,sample_x,1]
    active=(sample_x>49)&(sample_x<147)&(yy>136)&(yy<198)
    pigment=.79*np.clip((255-soft)/85,0,1)*active
    layer+=pigment[:,:,None]*(np.array((255,181,145))-layer)
    shine=np.clip((source-soft-3)/29,0,1)*active
    layer+=shine[:,:,None]*(255-layer)
    # Write RGB only; the face atlas's native alpha silhouette remains intact.
    a=np.array(face)
    a[:h,:w,:3]=np.rint(layer).clip(0,255).astype('uint8')
    # The starter's separate forehead/fringe overlay uses this UV island.
    # Our removable hair supplies that detail. Let the cheek show through
    # the donor overlay in every pose, including when the hair is hidden.
    a[236:360,190:291,3]=0
    return Image.fromarray(a,'RGBA')


def reference_iris_colors(rgba, iris, donor_red, upper, lower):
    """The native #4/#25 iris has a rounded highlight pool, with a hand-inked limbus."""
    light=np.clip((donor_red-100)/44,0,1)
    rgb=np.array(upper)+(np.array(lower)-np.array(upper))*light[:,:,None]
    rgba[iris,:3]=np.rint(rgb[iris]).clip(0,255).astype('uint8')
    tile=rgba[865:1024,750:898].copy()
    # Map the same lighting direction to the second horizontally mirrored UV.
    col=np.clip(1656-np.arange(750,898),750,896)
    amount=light[865:1024,col]
    mask=iris[865:1024,750:898]
    rgb=np.array(upper)+(np.array(lower)-np.array(upper))*amount[:,:,None]
    tile[mask,:3]=np.rint(rgb[mask]).clip(0,255).astype('uint8')
    return Image.fromarray(tile,'RGBA')


def paint(db, destination):
    destination.mkdir(parents=True, exist_ok=True)
    crown_paint(BLUE,(72,124,166),[(-.77,-.29,.24,.98,-.14),
        (-.35,.09,.19,.98,-.15),(.32,.85,.22,.99,-.11),
        (-1.30,-1.57,.42,.98,-.18),(1.45,1.66,.44,.98,-.16)],
        destination/'49-crown.png')
    size = 1024
    y, x = np.mgrid[:size, :size]
    height = 1 - y / (size - 1)
    longitude = 2 * np.pi * np.abs(x / (size - 1) - 0.5)
    border = np.interp(height, [0, .08, .30, .55, .78, 1], [.88, .84, .65, .585, .59, .81])
    distance = longitude - border
    base = np.empty((size, size, 3), np.uint8)
    base[:] = BLUE
    base[distance < .021] = (86, 151, 201)
    base[distance < .005] = (251, 251, 249)
    base[distance < -.015] = (255, 255, 255)
    body = Image.fromarray(base, 'RGB')
    mark = Image.open(db / 'data/Works_NumberTales/Images/DB_Primary/attr/numberMark/attr_numberMarkNTS-49.png').convert('RGBA')
    # UV width and height differ on the spherical upper chest.
    mark = mark.resize((43, 107), Image.Resampling.LANCZOS)
    decal=Image.new('RGBA',(size,size),(255,255,255,0))
    decal.paste(mark,(559,91))
    decal.save(destination/'49-chest-number.png')
    body.save(destination / '49-body.png')

    # Blend the cheek panel back into the blue flank, along the same direction
    # as the white bib. The new fill closes the native face's open rear perimeter.
    neck = np.empty((256,256,3),np.uint8)
    ny,nx=np.mgrid[:256,:256]
    vz=1-ny/255
    white=np.clip((.40-vz)/.25,0,1)
    white=white*white*(3-2*white)
    seam=(.064+.50*vz**1.5+.035*np.sin(vz*25)*np.exp(-((vz-.36)/.28)**2))*white
    neck[:] = BLUE
    neck[nx/255 < seam+.012*white] = (91,155,205)
    neck[nx/255 < seam] = (255,255,255)
    Image.fromarray(neck,'RGB').save(destination / '49-neck.png')

    base[:] = BLUE
    phase = 2 * np.pi * x / (size - 1)
    wave = .64 + .038 * np.sin(phase) + .024 * np.cos(2 * phase)
    base[height > wave] = LIGHT
    Image.fromarray(base, 'RGB').resize((256,512), Image.Resampling.LANCZOS).save(destination / '49-tail.png')

    src = Image.open(NATIVE / 'Corefolder-4/CoreFolder-4.png').convert('RGBA')
    rgba = np.array(src)
    red, green, blue = np.moveaxis(rgba[:,:,:3].astype(float), -1, 0)
    cyan = (green > red + 9) & (blue > red + 9)
    rgba[cyan, :3] = 255   # white backing and white muzzle of this Corefolder
    eye = (x > 750) & (x < 897) & (y > 865) & cyan
    second=reference_iris_colors(rgba,eye,red,(64,90,185),(67,120,195))
    # Existing overlay geometry remains available for every eyelid morph. Its
    # donor's two large white discs are replaced by #49's single iris catchlight.
    rgba[865:1024,899:1024,:] = 0
    face = Image.fromarray(rgba, 'RGBA')
    face.paste(second,(10,500))
    scale = 4
    for near,origin in [(True,(750,865)),(False,(10,500))]:
        pupil = Image.new('RGBA', (148*scale,159*scale))
        pen = ImageDraw.Draw(pupil)
        def poly(points, color):
            pts=[((u if near else 1656-u)-750,v-865) for u,v in points]
            pen.polygon([(round(u*scale),round(v*scale)) for u,v in pts],fill=color)
        poly([(831,890),(835,906),(837,928),(834,949),(827,969),(821,951),(819,933),(823,910)], (21,28,46,255))
        poly([(830,900),(833,916),(833,932),(830,948),(827,958),(824,944),(823,928),(826,913)], (189,138,230,255))
        if near:
            # In official expression 1, the near eye alone catches the light;
            # the fringe and upper lid frame the uninterrupted far iris.
            pen.ellipse((92*scale,38*scale,118*scale,62*scale), fill=(255,254,248,255))
        face.alpha_composite(pupil.resize((148,159),Image.Resampling.LANCZOS),origin)
    face=reference_cheeks(face,BLUE,3)
    face.save(destination / '49-face.png')
    # Trace the published isolated rear unit using its own nine differently
    # occluded lobes. Lower flank lobes run around the torso in the posed model.
    sys.path.insert(0,str(NATIVE/'Corefolder-Training'))
    import trace_tail_atlas as tracer
    tracer.PALETTES[49]=(BLUE,LIGHT)
    tracer.LANDMARKS[49]=[
        ((194,125),None,[]),((338,125),None,[]),
        ((85,150),None,[(95,77),(169,122),(233,206),(166,206),(85,178)]),
        ((447,150),None,[(438,77),(364,122),(300,206),(367,206),(448,178)]),
        ((126,253),None,[]),((410,253),None,[]),
        ((118,386),None,[(75,322),(170,263),(231,280),(209,365),(148,401)]),
        ((418,386),None,[(458,322),(363,263),(302,280),(324,365),(385,401)]),
        ((266,357),None,[])]
    tracer.bake(49,db,destination)
    # The unseen side of the curved plume can sample beyond a concave outline.
    # Extend the two actual fur colors through that margin without a painted
    # black skirt; its silhouette is supplied by the real volume and MToon.
    atlas=destination/'Tails-49.png'
    raw=np.asarray(Image.open(atlas).convert('RGB'),dtype=float)
    ratio=raw[:,:,0]/np.maximum(1.,raw[:,:,2])
    blend=np.clip((BLUE[0]-ratio*BLUE[2])/(ratio*(LIGHT[2]-BLUE[2])-(LIGHT[0]-BLUE[0])),0,1)
    restored=np.array(BLUE)+blend[:,:,None]*(np.array(LIGHT)-np.array(BLUE))
    Image.fromarray(np.rint(restored).astype('uint8'),'RGB').save(atlas)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('--out', type=Path, default=HERE)
    args = parser.parse_args()
    paint(args.database, args.out)

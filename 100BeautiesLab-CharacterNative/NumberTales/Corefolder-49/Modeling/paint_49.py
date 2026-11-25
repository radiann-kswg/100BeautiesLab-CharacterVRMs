"""Bake Yochika's editable UV maps from the official mark and the starter face UV layout."""
import argparse
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
NATIVE = HERE.parents[1]
BLUE = (106, 166, 215)
LIGHT = (155, 193, 230)


def paint(db, destination):
    destination.mkdir(parents=True, exist_ok=True)
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
    # The 2023 artwork shows a white collar of fur with two downward points.
    # Its upper edge opens into the white muzzle. Draw on the actual chest UV
    # so the marking stretches with the torso and remains beside the number.
    pen=ImageDraw.Draw(body)
    fur=[(483,61),(479,80),(477,99),(470,113),(460,124),(470,126),(480,125),(489,118),
         (489,131),(493,144),(494,162),(502,151),(508,142),(512,126),(516,141),(522,151),
         (528,162),(529,145),(534,131),(534,118),(542,124),(551,126),(558,124),
         (551,114),(546,99),(544,80),(540,61)]
    pen.polygon(fur,fill=(255,255,253))
    pen.line(fur[1:-1],fill=(192,188,185),width=2,joint='curve')
    mark = Image.open(db / 'data/Works_NumberTales/Images/DB_Primary/attr/numberMark/attr_numberMarkNTS-49.png').convert('RGBA')
    # UV width and height differ on the spherical upper chest.
    mark = mark.resize((43, 107), Image.Resampling.LANCZOS)
    body.paste(mark, (559, 91), mark.getchannel('A'))
    body.save(destination / '49-body.png')

    # Blend the cheek panel back into the blue flank, along the same direction
    # as the white bib. The new fill closes the native face's open rear perimeter.
    neck = np.empty((256,256,3),np.uint8)
    ny,nx=np.mgrid[:256,:256]
    vz=1-ny/255
    seam=.064+.50*vz**1.5+.035*np.sin(vz*25)*np.exp(-((vz-.36)/.28)**2)
    neck[:] = BLUE
    neck[nx/255 < seam+.012] = (91,155,205)
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
    rgba[eye & (red < 125), :3] = (64, 90, 185)
    rgba[eye & (red >= 125), :3] = (67, 120, 195)
    # Existing overlay geometry remains available for every eyelid morph. Its
    # donor's two large white discs are replaced by #49's single iris catchlight.
    rgba[865:1024,899:1024,:] = 0
    face = Image.fromarray(rgba, 'RGBA')
    scale = 4
    pupil = Image.new('RGBA', (140*scale, 155*scale))
    pen = ImageDraw.Draw(pupil)
    def poly(points, color):
        pen.polygon([(round((u-755)*scale),round((v-865)*scale)) for u,v in points],fill=color)
    poly([(828,891),(834,902),(839,928),(837,949),(829,969),(822,951),(820,933),(822,911)], (21,28,46,255))
    poly([(828,900),(833,915),(835,931),(833,948),(829,958),(825,945),(824,929),(825,913)], (189,138,230,255))
    pen.ellipse([(a*scale,b*scale) for a,b in [(88,17),(108,35)]], fill=(255,254,248,255))
    face.alpha_composite(pupil.resize((140,155),Image.Resampling.LANCZOS), (755,865))
    # The source UV cheek island is symmetric. Paint three fine peach strokes
    # over the soft canonical blush and mute its bubble highlights.
    cheek = np.array(face)
    mask = (x<202) & (y<238)
    d = ((x-96)/36)**2 + ((y-167)/16)**2
    for k, channel in enumerate((255, 217, 200)):
        cheek[:,:,k][mask] = (255-(255-channel)*.38*np.exp(-d[mask])).astype(np.uint8)
    face = Image.fromarray(cheek, 'RGBA')
    pen = ImageDraw.Draw(face)
    for cx in (82, 96, 108):
        pen.line([(cx-1,169),(cx+2,165)], fill=(248,176,143,255), width=2)
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

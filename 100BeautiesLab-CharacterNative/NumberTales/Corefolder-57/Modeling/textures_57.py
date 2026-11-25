"""Prepare Fivens' expression, fringe, body and armband maps from official art."""
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw

HERE=Path(__file__).resolve().parent
NATIVE=HERE.parents[1]
sys.path.insert(0,str(NATIVE/"Corefolder-6/Modeling"))
from eye_art import cheek_detail, prepare_eye_map
DB=Path("D:/VisualStudio Code Userfile/100BeautiesLab_CreationsDB/data/Works_NumberTales/Images/DB_Primary")


def prepare():
    # One continuous UV shell carries the ivory inner ear and the smaller pale pad.
    y,x=np.mgrid[:256,:512]
    t=1-(y+.5)/256
    angle=(x+.5)/512*2*np.pi
    half=np.interp(t,[0,.13,.28,.48,.74,.96,1],[0,.13,.54,.68,.62,.25,0])
    center=.91+.24*t
    ivory=np.clip((half-np.abs(angle-center))/.031,0,1)[:,:,None]
    pad_radius=((angle-.82)/.40)**2+((t-.36)/.115)**2
    inside=np.clip((1-pad_radius)*8,0,1)[:,:,None]*ivory
    base=(1-ivory)*np.array([255,238,98])+ivory*np.array([255,253,242])
    Image.fromarray(np.uint8(np.round((1-inside)*base+inside*np.array([239,244,173])))).save(HERE/'Fivens-Ear.png',optimize=True)
    im=Image.open(NATIVE/"Corefolder-4/CoreFolder-4.png").convert("RGBA")
    pixels=np.array(im)
    red,green,blue=pixels[:,:,:3].astype(float).transpose(2,0,1)
    pixels[(green-red>9)&(blue-red>9),:3]=255
    pixels[865:1024,753:898,:]=0
    pixels[872:,898:,3]=0
    im=Image.fromarray(pixels)
    prepare_eye_map(57, HERE/"Fivens-Eyes.png")
    cheek_detail(im,57)
    im.save(HERE/"Fivens-Face.png",optimize=True)
    h,w=384,768
    y,x=np.mgrid[:h,:w]
    height=.713*(1-(y+.5)/h)
    a=np.abs(((x+.5)/w-.5)*2*np.pi)
    # Sampled #93 / #16 belly cross-sections give the lower sweep.
    # Fivens has a broader white front and a gold gap before the armband.
    levels=[.014,.025,.040,.060,.100,.160,.250,.370,.460,.510,.575,.630,.713]
    angles=[0,.17,.30,.41,.49,.55,.61,.64,.63,.60,.575,.56,.55]
    width=np.sqrt(np.interp(height,levels,np.square(angles)))
    blend_at_foot=np.clip((height-.014)/.007,0,1)[...,None]
    gold=np.clip((width+.030-a)/.018,0,1)[...,None]*blend_at_foot
    ivory=np.clip((width-a)/.013,0,1)[...,None]*blend_at_foot
    fur=(1-gold)*np.array([255,238,98])+gold*np.array([242,224,104])
    Image.fromarray(np.uint8(np.round((1-ivory)*fur+ivory*255))).save(HERE/"Fivens-Fur.png",optimize=True)
    # Bake the supplied digits into the band; use one curved, skinned surface for the print and piping.
    band=Image.new("RGBA",(480,256),"white")
    d=ImageDraw.Draw(band)
    d.rectangle((0,17,479,26),fill="#d7d345")
    d.rectangle((0,229,479,238),fill="#d7d345")
    mark=Image.open(DB/"attr/numberMark/attr_numberMarkNTS-57.png").convert("RGBA")
    mark.thumbnail((153,164),Image.Resampling.LANCZOS)
    band.alpha_composite(mark,((480-mark.width)//2,(256-mark.height)//2))
    band.save(HERE/"Fivens-Armband.png",optimize=True)


if __name__=="__main__":
    prepare()

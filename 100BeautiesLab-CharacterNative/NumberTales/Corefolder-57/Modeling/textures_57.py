"""Prepare Fivens' expression, fringe, body and armband maps from official art."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE=Path(__file__).resolve().parent
NATIVE=HERE.parents[1]
DB=Path("D:/VisualStudio Code Userfile/100BeautiesLab_CreationsDB/data/Works_NumberTales/Images/DB_Primary")


def prepare():
    im=Image.open(NATIVE/"Corefolder-4/CoreFolder-4.png").convert("RGBA")
    pixels=np.array(im)
    red,green,blue=pixels[:,:,:3].astype(float).transpose(2,0,1)
    pixels[(green-red>9)&(blue-red>9),:3]=255
    pixels[865:1024,753:898,:]=0
    pixels[872:,898:,3]=0
    im=Image.fromarray(pixels)
    # The lower rim is flat. Pose 2 has a divided olive/yellow-green iris; pose 1
    # shows the narrow blue pupil specified in the database.
    eye=Image.new("RGBA",(152*3,160*3))
    pen=ImageDraw.Draw(eye)
    def poly(p,fill):pen.polygon([(int(x*3),int(y*3)) for x,y in p],fill=fill)
    poly([(19,35),(33,14),(56,6),(88,6),(110,14),(126,31),(132,55),(132,96),(123,128),
          (118,139),(30,139),(20,127),(12,92),(11,56)],"#211d24")
    poly([(25,39),(37,22),(57,14),(85,14),(105,22),(118,39),(124,58),(124,94),
          (116,126),(112,131),(35,131),(27,119),(20,92),(19,56)],"#a6bc40")
    poly([(21,97),(43,94),(83,95),(122,99),(116,125),(112,131),(35,131),(27,119)],"#e8f152")
    poly([(79,30),(87,35),(94,52),(94,81),(87,104),(79,116),(71,111),(66,92),(65,62),(70,42)],"#21202a")
    poly([(79,39),(84,45),(87,59),(86,81),(81,99),(78,104),(73,93),(73,67),(75,48)],"#4b79be")
    pen.ellipse((84*3,29*3,101*3,49*3),fill="#fffcf0")
    im.alpha_composite(eye.resize((152,160),Image.Resampling.LANCZOS),(750,862))
    patch=Image.new("RGB",(500,290),"white")
    pen=ImageDraw.Draw(patch)
    for k in range(4):
        x=117+47*k
        pen.line((x,155,x+36,118),fill="#ed9f7a",width=8)
    im.paste(patch.resize((100,58),Image.Resampling.LANCZOS),(50,137))
    im.save(HERE/"Fivens-Face.png",optimize=True)
    art=np.array(Image.open(DB/"corefolder/57/emstk_corefolderNTS-57-1.png").convert("RGBA"))
    y,x=np.mgrid[:432,:700]
    wx=(x+.5)/700*.62-.31
    wz=1.08-(y+.5)/432*.33
    # Landmarks, from native 1459 x 1427 pose 1, are the wink and visible iris.
    sx=(692+1260*wx).round().astype(int)
    sy=(480-1260*(wz-.81)).round().astype(int)
    rgba=art[sy,sx].astype(float)
    r,g,b=rgba[:,:,:3].transpose(2,0,1)
    alpha=np.clip((r-b-85)/45,0,1)*np.clip((r-g+1)/7,0,1)*np.clip((r-150)/62,0,1)
    alpha*=np.clip((g-177)/27,0,1)*np.clip((g-b-83)/26,0,1)
    labels,n=ndimage.label(alpha>.15)
    largest=1+np.argmax(np.bincount(labels.ravel())[1:])
    island=labels==largest
    alpha*=ndimage.binary_dilation(island,iterations=1)
    gaps=ndimage.binary_fill_holes(island)&~island
    gap_labels,_=ndimage.label(gaps)
    areas=np.bincount(gap_labels.ravel())
    repair=gaps&(areas[gap_labels]<1150)
    rgba[repair,:3]=[225,211,83]
    alpha[repair]=1
    rgba[:,:,3]=255*alpha
    rgba[:,:,:3]=np.where((alpha>.06)[:,:,None],rgba[:,:,:3],[255,238,98])
    Image.fromarray(np.uint8(rgba)).save(HERE/"Fivens-Fringe.png",optimize=True)
    h,w=384,768
    y,x=np.mgrid[:h,:w]
    z=1-(y+.5)/h
    a=np.abs(((x+.5)/w-.5)*2*np.pi)
    width=np.interp(z,[0,.10,.30,.55,.76,1],[.68,.66,.59,.48,.44,.56])
    gold=np.clip((width+.033-a)/.012,0,1)[...,None]
    ivory=np.clip((width-a)/.011,0,1)[...,None]
    fur=(1-gold)*np.array([255,238,98])+gold*np.array([220,204,71])
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

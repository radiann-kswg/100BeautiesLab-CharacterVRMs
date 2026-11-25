"""Extract a separately observed iris for each eye in the NumberTales drawings."""
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np


# Polygon coordinates refer to unmodified image pixels. Order is screen left, screen right.
# Both cores show the white reflection on screen right.
EYES={
    6:(
        ("corefolder/6/emstk_corefolderNTS-6-1.png",8,
         [(690,354),(699,342),(711,334),(722,331),(734,333),(747,337),(758,346),
          (764,354),(763,365),(763,378),(758,394),(751,407),(745,417),
          (730,414),(711,410),(693,405),(687,398),(684,385),(685,369)]),
        ("corefolder/6/emstk_corefolderNTS-6-1.png",8,
         [(919,382),(925,371),(936,365),(947,366),(962,369),(979,375),(991,382),
          (997,392),(995,404),(996,416),(993,431),(985,448),(982,451),
          (966,447),(947,444),(929,441),(922,434),(917,421),(915,403)])),
    57:(
        # The catalogue's Rough Design panel depicts the corefolder with both eyes open.
        # The large corefolder pose 1 closes this eye.
        ("catalog/chr-dsgn_catalogNTS-57.png",5,
         [(7464,2677),(7468,2676),(7476,2678),(7483,2680),(7488,2684),(7488,2690),
          (7489,2693),(7489,2703),(7487,2714),(7484,2719),(7468,2717),
          (7464,2713),(7461,2707),(7460,2702),(7460,2693),(7461,2686)]),
        ("corefolder/57/emstk_corefolderNTS-57-1.png",0,
         [(799,469),(803,455),(815,454),(829,454),(841,456),(854,460),(858,467),
          (855,476),(860,486),(862,498),(861,514),(857,529),(854,538),
          (805,537),(799,528),(796,516),(795,496),(796,481)]))
}


def catalogue_left_57():
    """Re-ink the 29 px catalogue eye using its sampled outlines and the other eye's stroke width."""
    factor=3
    patch=Image.new('RGBA',(256*factor,256*factor))
    pen=ImageDraw.Draw(patch)

    def region(points,colour):
        p=np.array(points,dtype=float)
        curve=[]
        for j in range(len(p)):
            a,b,c,d=(p[k%len(p)] for k in (j-1,j,j+1,j+2))
            for t in np.arange(0,1,.125):
                q=(2*t**3-3*t*t+1)*b+(t**3-2*t*t+t)*.34*(c-a)+(-2*t**3+3*t*t)*c+(t**3-t*t)*.34*(d-b)
                curve.append(tuple(q*factor))
        pen.polygon(curve,fill=colour)

    ink='#070708'
    region([(32,26),(70,10),(116,12),(168,21),(212,38),(229,52),(229,75),(222,86),(233,104),
            (242,145),(242,180),(236,210),(222,239),(204,245),(79,240),(53,223),(31,191),
            (17,151),(15,107),(19,70)],ink)
    region([(45,37),(76,24),(113,23),(158,31),(203,44),(214,63),(208,86),(221,115),
            (229,152),(228,183),(220,208),(211,229),(86,226),(65,213),(45,185),(30,149),
            (28,109),(33,71)],'#acbf40')
    region([(31,139),(75,126),(125,115),(174,107),(216,112),(228,153),(227,186),
            (217,215),(209,228),(87,225),(66,213),(44,184)],'#eff151')
    region([(151,47),(168,49),(179,68),(179,108),(176,143),(164,172),(151,190),
            (138,194),(126,181),(116,156),(116,126),(123,96),(134,66)],ink)
    region([(150,65),(158,62),(166,76),(166,111),(163,140),(154,160),(145,174),
            (138,178),(131,163),(128,142),(131,116),(138,90)],'#477bbf')
    region([(160,42),(178,36),(204,38),(224,47),(233,59),(232,77),(224,83),
            (209,80),(196,89),(177,94),(157,90),(145,79),(145,61)],ink)
    region([(168,49),(183,46),(204,47),(221,54),(226,61),(226,72),(216,75),
            (206,70),(194,78),(179,83),(164,80),(156,72),(158,58)],'#ffffff')
    return patch.resize((246,246),Image.Resampling.LANCZOS)


def prepare_eye_map(number,images,out):
    board=Image.new("RGBA",(512,256),(255,255,255,0))
    for j,(file,roll,points) in enumerate(EYES[number]):
        with Image.open(Path(images)/file) as source:
            x0=min(x for x,y in points)-2
            y0=min(y for x,y in points)-2
            box=(x0,y0,max(x for x,y in points)+3,max(y for x,y in points)+3)
            patch=source.crop(box).convert("RGBA")
        # The trim only isolates the iris from the adjoining lashes and sclera.
        scale=4
        mask=Image.new("L",(patch.width*scale,patch.height*scale))
        ImageDraw.Draw(mask).polygon([((x-x0)*scale,(y-y0)*scale) for x,y in points],fill=255)
        patch.putalpha(mask.resize(patch.size,Image.Resampling.LANCZOS))
        if roll:patch=patch.rotate(roll,Image.Resampling.BICUBIC,expand=True)
        patch=patch.crop(patch.getchannel("A").point(lambda v:255 if v>70 else 0).getbbox())
        patch=patch.resize((246,246),Image.Resampling.LANCZOS)
        if number==57 and j==0:patch=catalogue_left_57()
        board.alpha_composite(patch,(j*256+5,5))
    board.save(out,optimize=True)

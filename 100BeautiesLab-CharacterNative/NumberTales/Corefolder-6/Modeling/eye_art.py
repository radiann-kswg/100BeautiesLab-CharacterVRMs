"""Draw two independent reference-VRM-style irises from the character's visual attributes."""
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


def iris(number,cell):
    ss=4
    y,x=np.mgrid[:256*ss,:256*ss]/ss
    lean=(-.025,.035)[cell]
    xx=(x-128-(y-128)*lean)/115
    yy=(y-128)/121
    radius=(abs(xx)**2.15+abs(yy)**2.15)**(1/2.15)
    # #16's lightly outlined oval and pastel two-tone fill also appear on #93.
    top,bottom=((180,155,188),(138,190,226)) if number==6 else ((168,187,77),(228,235,102))
    edge=122-14*(1-xx*xx)+(-6,4)[cell]*xx
    t=np.clip((y-edge)/2.4,0,1)[:,:,None]
    rgb=(1-t)*np.array(top)+t*np.array(bottom)
    ink=np.array([53,47,57])
    outline=np.clip((radius-.953)/.012,0,1)[:,:,None]
    a=np.uint8(np.clip((1-radius)/.008,0,1)*255)
    arr=np.dstack((np.uint8((1-outline)*rgb+outline*ink),a))
    im=Image.fromarray(arr)
    pen=ImageDraw.Draw(im)
    def curve(points,fill):
        ring=np.asarray(points,float)
        result=[]
        for j in range(len(ring)):
            a,b,c,d=(ring[k%len(ring)] for k in (j-1,j,j+1,j+2))
            for t in np.arange(0,1,.125):
                p=(2*t**3-3*t*t+1)*b+(t**3-2*t*t+t)*.35*(c-a)+(-2*t**3+3*t*t)*c+(t**3-t*t)*.35*(d-b)
                result.append(tuple(p*ss))
        pen.polygon(result,fill=fill)
    if number==6:
        cx,cy=((125,144),(120,150))[cell]
        def star(w,h,fill):
            points=((0,-h),(.35*w,-.32*h),(w,0),(.34*w,.32*h),(0,h),(-.35*w,.32*h),(-w,0),(-.34*w,-.32*h))
            curve([(cx+px,cy+py) for px,py in points],fill)
        # #22 places its identifying geometry inside a single fine iris perimeter.
        star(39,62,'#514958');star(32,53,'#fffdfb')
        hx,hy=((177,57),(189,67))[cell]
    else:
        # #93's narrow vertical pupil stays distinct through the two filled bands.
        cx,cy=((131,130),(139,132))[cell]
        def slit(w,h,fill):
            points=((1,-1),(.75,-.82),(1,-.30),(.90,.25),(.35,.82),(-.25,1),(-.68,.77),(-.91,.24),(-.79,-.34),(-.24,-.8))
            curve([(cx+u*w-(v*h)*.09,cy+v*h) for u,v in points],fill)
        slit(22,68,'#494850');slit(17,61,'#547fbb')
        hx,hy=((174,57),(184,64))[cell]
    r=(18,19)[cell]
    for rad,color in ((r+2.5,'#554e59'),(r,'#fffefd')):
        pen.ellipse(tuple(ss*v for v in (hx-rad,hy-rad,hx+rad,hy+rad)),fill=color)
    return im.resize((256,256),Image.Resampling.LANCZOS)


def prepare_eye_map(number,out):
    # The source landmarks above document feature identity and light direction.
    # No pixels from the flat illustration are used in the VRM iris texture.
    board=Image.new('RGBA',(512,256))
    for cell in (0,1):board.alpha_composite(iris(number,cell),(cell*256,0))
    board.save(out,optimize=True)


def cheek_detail(image,number):
    """Keep the soft reference blush and add the character's restrained hatch accent."""
    area=(49,133,145,202)
    native=image.crop(area).convert('RGBA')
    paper=Image.new('RGBA',native.size,'white')
    native=Image.blend(paper,native,.72 if number==6 else .66)
    scale=4
    layer=Image.new('RGBA',(native.width*scale,native.height*scale))
    pen=ImageDraw.Draw(layer)
    for x,y in ((77,160),(87,163),(97,166),(107,169)):
        x-=area[0];y-=area[1]
        pen.line(((x-2)*scale,(y+2)*scale,(x+3)*scale,(y-3)*scale),fill=(227,142,111,92),width=4)
    native.alpha_composite(layer.resize(native.size,Image.Resampling.LANCZOS))
    image.paste(native,area[:2])

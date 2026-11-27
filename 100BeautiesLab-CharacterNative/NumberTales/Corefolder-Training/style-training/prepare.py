"""Prepare traceable image-LoRA examples; preserve whole views with padding, no flips."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageOps
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
NATIVE=HERE.parent.parent
IDS=(4,16,20,22,25,93)
COLORS={4:'cyan hair and body, turquoise eyes, a shoulder cape, multiple stylized tails',16:'pink hair and body, a blue cat ear hat, a ponytail, multiple stylized tails',20:'white hair and body, golden eyes, multiple stylized tails',22:'yellow hair and body, golden eyes, floating rings, multiple stylized tails',25:'gray blue hair and body, blue green eyes, a green scarf, multiple stylized tails',93:'pale yellow hair and body, golden eyes, a white ribbon, multiple stylized tails'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare():
    out=HERE/'dataset-v1';out.mkdir(exist_ok=True)
    rows=[];records=[]
    def add(name,im,caption,role,sources):
        # Whole-image training preprocessing. No generated pixels, content crops or horizontal flips.
        bg=im.getpixel((0,0))
        canvas=ImageOps.pad(im.convert('RGB'),(768,768),color=bg,method=Image.Resampling.LANCZOS)
        target=out/name;canvas.save(target)
        rows.append({'file_name':name,'text':caption})
        records.append({'file_name':name,'role':role,'sha256':sha(target),'caption':caption,'sources':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in sources]})
    for n in IDS:
        sources=[HERE/'captures'/f'Corefolder-{n}'/f'{view}.png' for view in ('front','side','back')]
        images=[Image.open(p).convert('RGB') for p in sources]
        for view,im,p in zip(('front','side','back'),images,sources):
            add(f'vrm-{n}-{view}.png',im,f'nt_vrmstyle, orthographic {view} view of NumberTales Corefolder character {n}, a round stylized chibi animal character, {COLORS[n]}, painted anime face texture, MToon flat shaded VRM model, neutral gray background','canonical_vrm_style',[p])
        strip=Image.new('RGB',(3072,1024),(191,191,191))
        for i,im in enumerate(images):strip.paste(im,(1024*i,0))
        strip.save(HERE/'captures'/f'Corefolder-{n}'/'three-view.png')
        add(f'vrm-{n}-three-view.png',strip,f'nt_vrmstyle, three view model sheet, front side and back views of NumberTales Corefolder character {n}, a round stylized chibi animal character, {COLORS[n]}, painted anime face texture, MToon flat shaded VRM model, neutral gray background','canonical_vrm_style',sources)
    for n,desc in [(57,'golden yellow fox ears and ponytail, amber eyes, white belly, seven tails, an armband numbered 57 on the right shoulder'),(85,'brown fox ears and ponytail, cyan eyes, white belly, eight tails, a cyan teardrop pendant')]:
        p=NATIVE/f'Corefolder-{n}'/'Training'/f'ThreeView-CoreFolder-{n}.png'
        add(f'design-{n}.png',Image.open(p),f'nt_designreference, a generated character design sheet with two rows of front side and back views, NumberTales Corefolder character {n}, {desc}, white background','generated_target_design',[p])
    (out/'metadata.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    (HERE/'dataset-manifest.json').write_text(json.dumps({'version':1,'canonical_ids':IDS,'examples':len(rows),'style_examples':24,'target_design_examples':2,'preprocessing':'RGB, whole image padded to 768 square; no random or horizontal flip augmentation','split':'training only; before/after samples are qualitative, not a held-out generalization test','records':records},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'images':len(rows),'output':str(out)},ensure_ascii=True))
if __name__=='__main__':prepare()

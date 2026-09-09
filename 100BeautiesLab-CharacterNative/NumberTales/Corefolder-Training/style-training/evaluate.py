"""Compare the actual trained LoRA with its base model, identical prompts and seeds."""
import argparse,json,time,hashlib,os
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['HF_HOME']=str(ROOT/'.cache/huggingface')
import torch
from diffusers import StableDiffusionXLPipeline,StableDiffusionXLImg2ImgPipeline
from PIL import Image

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--run',default='style-lora-v2');cli.add_argument('--resolution',type=int,default=1024);cli.add_argument('--mode',choices=['text','design'],default='text');args=cli.parse_args()
    run=HERE.parent/'runs'/args.run;weights=run/'pytorch_lora_weights.safetensors'
    if not weights.exists():weights=HERE/'models'/f'{args.run}.safetensors'
    if not weights.exists():raise FileNotFoundError(weights)
    out=HERE/'evaluation'/(f'{args.run}-{args.resolution}' if args.mode=='text' else f'{args.run}-design-{args.resolution}');out.mkdir(parents=True,exist_ok=True)
    cls=StableDiffusionXLPipeline if args.mode=='text' else StableDiffusionXLImg2ImgPipeline
    pipe=cls.from_pretrained(ROOT/'.cache/sdxl-base',torch_dtype=torch.float16,variant='fp16',local_files_only=True)
    pipe.enable_model_cpu_offload();pipe.enable_vae_slicing()
    prompts={
        57:'nt_vrmstyle, one single round chibi fox spirit, full body front view, centered, golden yellow fur and ponytail, fox ears, amber anime eyes, white belly, seven tails, white armband on right shoulder, flat cel shading, neutral gray background',
        85:'nt_vrmstyle, one single round chibi fox spirit, full body front view, centered, brown fur and ponytail, fox ears, cyan anime eyes, white belly, eight tails, cyan teardrop pendant, flat cel shading, neutral gray background',
    }
    if args.mode=='design':
        prompts={57:'nt_vrmstyle, three view model sheet, front side back, round chibi fox spirit, golden yellow ponytail and fur, amber anime eyes, white belly, seven tails, shoulder armband, MToon flat cel shading',85:'nt_vrmstyle, three view model sheet, front side back, round chibi fox spirit, brown ponytail and fur, cyan anime eyes, white belly, eight tails, cyan teardrop pendant, MToon flat cel shading'}
    records=[];start=time.time()
    for stage in ('base','lora'):
        if stage=='lora':pipe.load_lora_weights(str(weights.parent),weight_name=weights.name);pipe.fuse_lora(lora_scale=.8)
        for n,prompt in prompts.items():
            path=out/f'{n}-{stage}.png'
            kwargs={'height':args.resolution,'width':args.resolution}
            source=None
            negative='photorealistic, glossy plastic, metallic, realistic fur, human body, long legs, duplicate character, cropped, texture atlas, grid, collage, multiple views, multiple characters'
            if args.mode=='design':
                source=HERE.parent.parent/f'Corefolder-{n}'/'Training'/f'ThreeView-CoreFolder-{n}.png'
                ref=Image.open(source).convert('RGB');h=int(ref.height*args.resolution/ref.width)//8*8
                kwargs={'image':ref.resize((args.resolution,h),Image.Resampling.LANCZOS),'strength':.3}
                negative='photorealistic, glossy plastic, metallic, realistic fur, human body, long legs, armor, robe, extra accessories, cropped'
            im=pipe(prompt=prompt,negative_prompt=negative,num_inference_steps=30,guidance_scale=5.5,generator=torch.Generator('cpu').manual_seed(2026),**kwargs).images[0]
            im.save(path)
            records.append({'id':n,'stage':stage,'mode':args.mode,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest() if source else None,'strength':.3 if source else None,'prompt':prompt,'seed':2026,'steps':30,'resolution':args.resolution,'guidance_scale':5.5,'lora_scale':.8 if stage=='lora' else 0,'image':str(path.relative_to(HERE)).replace('\\','/'),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (out/'comparison.json').write_text(json.dumps({'purpose':'qualitative matched-seed diagnostic, not official character designs or VRM output','elapsed_seconds':time.time()-start,'lora_sha256':hashlib.sha256(weights.read_bytes()).hexdigest(),'samples':records},indent=2),encoding='utf-8')
    print(json.dumps({'samples':len(records),'output':str(out)},ensure_ascii=True))
if __name__=='__main__':main()

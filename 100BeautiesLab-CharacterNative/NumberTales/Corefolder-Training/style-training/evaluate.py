"""Compare the actual trained LoRA with its base model, identical prompts and seeds."""
import argparse,json,time,hashlib,os
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['HF_HOME']=str(ROOT/'.cache/huggingface')
import torch
from diffusers import StableDiffusionXLPipeline

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--run',default='style-lora-v2');args=cli.parse_args()
    run=HERE.parent/'runs'/args.run;weights=run/'pytorch_lora_weights.safetensors'
    if not weights.exists():raise FileNotFoundError(weights)
    out=HERE/'evaluation'/args.run;out.mkdir(parents=True,exist_ok=True)
    pipe=StableDiffusionXLPipeline.from_pretrained(ROOT/'.cache/sdxl-base',torch_dtype=torch.float16,variant='fp16',local_files_only=True)
    pipe.enable_model_cpu_offload();pipe.enable_vae_slicing()
    prompts={
        57:'nt_vrmstyle, orthographic front view of NumberTales Corefolder character 57, a round stylized chibi fox character, golden yellow hair in a ponytail, fox ears, amber eyes, white belly, seven stylized tails, armband numbered 57 on the right shoulder, painted anime face texture, MToon flat shaded VRM model, neutral gray background',
        85:'nt_vrmstyle, orthographic front view of NumberTales Corefolder character 85, a round stylized chibi fox character, brown hair in a ponytail, fox ears, cyan eyes, white belly, eight stylized tails, cyan teardrop pendant, painted anime face texture, MToon flat shaded VRM model, neutral gray background',
    }
    records=[];start=time.time()
    for stage in ('base','lora'):
        if stage=='lora':pipe.load_lora_weights(str(run),weight_name=weights.name);pipe.fuse_lora(lora_scale=.8)
        for n,prompt in prompts.items():
            path=out/f'{n}-{stage}.png'
            im=pipe(prompt=prompt,negative_prompt='photorealistic, glossy plastic, metallic, realistic fur, human body, long legs, duplicate character, cropped',height=512,width=512,num_inference_steps=30,guidance_scale=5.5,generator=torch.Generator('cpu').manual_seed(2026)).images[0]
            im.save(path)
            records.append({'id':n,'stage':stage,'prompt':prompt,'seed':2026,'steps':30,'guidance_scale':5.5,'lora_scale':.8 if stage=='lora' else 0,'image':str(path.relative_to(HERE)).replace('\\','/'),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (out/'comparison.json').write_text(json.dumps({'purpose':'qualitative matched-seed diagnostic, not official character designs or VRM output','elapsed_seconds':time.time()-start,'lora_sha256':hashlib.sha256(weights.read_bytes()).hexdigest(),'samples':records},indent=2),encoding='utf-8')
    print(json.dumps({'samples':len(records),'output':str(out)},ensure_ascii=True))
if __name__=='__main__':main()

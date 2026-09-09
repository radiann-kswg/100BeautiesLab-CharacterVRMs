"""Restore the pinned upstream trainer and SDXL base model into ignored local cache."""
import os,json,hashlib,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
os.environ['HF_HOME']=str(ROOT/'.cache/huggingface')
from huggingface_hub import snapshot_download
s=json.loads((HERE/'training-sources.json').read_text(encoding='utf-8-sig'))
script=urllib.request.urlopen(s['training_script_url'],timeout=60).read()
assert hashlib.sha256(script).hexdigest()==s['training_script_sha256']
(ROOT/'.cache').mkdir(exist_ok=True);(ROOT/'.cache/train_text_to_image_lora_sdxl.py').write_bytes(script)
patterns=['model_index.json','scheduler/*','tokenizer/*','tokenizer_2/*','text_encoder/config.json','text_encoder/model.fp16.safetensors','text_encoder_2/config.json','text_encoder_2/model.fp16.safetensors','unet/config.json','unet/diffusion_pytorch_model.fp16.safetensors','vae/config.json','vae/diffusion_pytorch_model.fp16.safetensors']
snapshot_download(repo_id=s['repo'],revision=s['revision'],allow_patterns=patterns,local_dir=str(ROOT/'.cache/sdxl-base'),max_workers=4)
print('Pinned training sources ready')

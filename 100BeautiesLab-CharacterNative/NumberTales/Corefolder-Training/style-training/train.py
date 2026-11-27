"""Run the pinned official Diffusers SDXL LoRA trainer and record local resource use."""
import argparse,hashlib,importlib.util,json,os,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
os.environ['HF_HOME']=str(ROOT/'.cache/huggingface')
os.environ['HF_HUB_OFFLINE']='0'  # Diffusers' final local LoRA lookup requires this; no Hub upload is enabled.
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'

def main():
    cli=argparse.ArgumentParser();cli.add_argument('--steps',type=int,default=400);cli.add_argument('--name',default='style-lora-v1');cli.add_argument('--resolution',type=int,default=512)
    cfg=cli.parse_args()
    if cfg.steps<1 or not cfg.name.replace('-','').replace('_','').isalnum():raise ValueError('Invalid run name or step count')
    source=json.loads((HERE/'training-sources.json').read_text())
    script=ROOT/'.cache/train_text_to_image_lora_sdxl.py'
    assert hashlib.sha256(script.read_bytes()).hexdigest()==source['training_script_sha256']
    out=HERE.parent/'runs'/cfg.name
    if (out/'pytorch_lora_weights.safetensors').exists():raise FileExistsError('Refusing to overwrite trained weights')
    args=['--pretrained_model_name_or_path',str(ROOT/'.cache/sdxl-base'),'--variant','fp16','--train_data_dir',str(HERE/'dataset-v1'),'--caption_column','text','--resolution',str(cfg.resolution),'--center_crop','--train_batch_size','1','--gradient_accumulation_steps','1','--gradient_checkpointing','--max_train_steps',str(cfg.steps),'--learning_rate','0.0001','--lr_scheduler','constant','--lr_warmup_steps','0','--rank','4','--mixed_precision','fp16','--dataloader_num_workers','0','--report_to','tensorboard','--seed','2026','--checkpointing_steps','1000','--output_dir',str(out)]
    spec=importlib.util.spec_from_file_location('official_sdxl_trainer',script);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    import torch
    torch.cuda.reset_peak_memory_stats();started=time.time()
    sys.argv=[str(script)]+args
    module.main(module.parse_args())
    from safetensors.torch import load_file
    weights=out/'pytorch_lora_weights.safetensors';state=load_file(weights)
    b=[v for k,v in state.items() if '.lora_B.' in k or '.lora.up.' in k]
    if not b or not all(torch.isfinite(v).all() for v in state.values()) or not any(torch.count_nonzero(v)>0 for v in b):raise RuntimeError('LoRA weight validation failed')
    report={'steps':cfg.steps,'resolution':cfg.resolution,'elapsed_seconds':time.time()-started,'gpu':torch.cuda.get_device_name(),'peak_allocated_gib':torch.cuda.max_memory_allocated()/2**30,'peak_reserved_gib':torch.cuda.max_memory_reserved()/2**30,'sha256':hashlib.sha256(weights.read_bytes()).hexdigest(),'bytes':weights.stat().st_size,'tensor_count':len(state),'nonzero_B_tensors':sum(bool(torch.count_nonzero(v)) for v in b),'finite_weights':True,'training_sources':source,'dataset_manifest_sha256':hashlib.sha256((HERE/'dataset-manifest.json').read_bytes()).hexdigest(),'arguments':args,'cloud_cost_jpy':0}
    (out/'run-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
if __name__=='__main__':main()

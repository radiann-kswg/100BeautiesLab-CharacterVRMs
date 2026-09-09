"""Check provenance, full-body visibility and the exact training set; no source writes."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    sources=json.loads((HERE/'source-vrms.json').read_text(encoding='utf-8-sig'))
    assert {r['id'] for r in sources}=={4,16,20,22,25,93}
    report={'source_vrms_unchanged':True,'captures':[]}
    for r in sources:
        assert sha(ROOT/r['source'])==r['sha256'],r['source']
        for view in ('front','side','back'):
            p=HERE/'captures'/f"Corefolder-{r['id']}"/f'{view}.png'
            a=np.array(Image.open(p).convert('RGB'));assert a.shape==(1024,1024,3)
            fg=np.max(abs(a.astype(int)-a[0,0].astype(int)),axis=2)>12
            ys,xs=np.where(fg);ratio=float(fg.mean())
            assert ratio>.03 and xs.min()>2 and xs.max()<1021 and ys.min()>2 and ys.max()<1021,(p,ratio)
            report['captures'].append({'id':r['id'],'view':view,'foreground_fraction':ratio,'bounds_pixels':[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())],'sha256':sha(p)})
    dataset=json.loads((HERE/'dataset-manifest.json').read_text())
    assert len(dataset['records'])==26
    for r in dataset['records']:
        assert sha(HERE/'dataset-v1'/r['file_name'])==r['sha256']
        for src in r['sources']:assert sha(ROOT/src['path'])==src['sha256']
    assert sum(r['role']=='canonical_vrm_style' for r in dataset['records'])==24
    assert sum(r['role']=='generated_target_design' for r in dataset['records'])==2
    capture=json.loads((HERE/'captures/capture-manifest.json').read_text())
    assert capture['outlineRendererFeature']=='MToonOutlineRenderFeature'
    report['dataset_hashes_valid']=True;report['training_examples']=26;report['outline_capture_enabled']=True
    (HERE/'data-checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'unchanged_sources':6,'valid_captures':18,'validated_training_images':26,'outline_capture_enabled':True}))
if __name__=='__main__':main()

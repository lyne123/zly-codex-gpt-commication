"""保存Baseline实际使用的四份OOC IP及顶层综合检查点，不修改源文件。"""
from pathlib import Path
import hashlib
import json
import shutil

root=Path(__file__).resolve().parents[1]
records=[]
for ip in ['clk_wiz_0','fifo_tdc_result','ila_2','ila_3','synth_1']:
    name='tdc_meas_top' if ip=='synth_1' else ip
    run=ip if ip=='synth_1' else ip+'_synth_1'
    source=root/'build/baseline/timing_baseline.runs'/run/(name+'.dcp')
    target=root/'inputs/baseline_synthesis_products'/(name+'.dcp')
    target.parent.mkdir(parents=True,exist_ok=True)
    assert not target.exists(),'拒绝覆盖已保存依赖'
    shutil.copyfile(source,target)
    with source.open('rb') as f:before=hashlib.file_digest(f,'sha256').hexdigest()
    with target.open('rb') as f:after=hashlib.file_digest(f,'sha256').hexdigest()
    assert before==after
    records.append(dict(source=str(source),archived=str(target.relative_to(root)),sha256=after,bytes=target.stat().st_size))
(root/'inputs/BASELINE_SYNTHESIS_PRODUCTS_PROVENANCE.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print('保存实际综合依赖',len(records))

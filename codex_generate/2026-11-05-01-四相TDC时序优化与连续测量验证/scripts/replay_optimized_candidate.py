"""用未改候选RTL重放新SDF原始帧，并与真实候选逐事件精确对照。"""
from pathlib import Path
import csv
import hashlib
import json
import subprocess

root=Path('U:/')
source=root/'sim/tb_candidate_replay.sv'
bench=root/'sim/tb_candidate_replay_optimized.sv'
text=source.read_text(encoding='utf-8').replace('T:/results/baseline/gate_validation/raw.csv','U:/results/optimized/baseline/gate_validation/raw.csv')
text=text.replace('U:/results/candidate_replay.csv','U:/results/optimized_candidate_replay.csv').replace('U:/results/candidate_replay_pipeline.csv','U:/results/optimized_candidate_replay_pipeline.csv')
assert not (root/'results/optimized_candidate_replay.csv').exists(),'拒绝覆盖重放证据'
bench.write_text(text,encoding='utf-8')
commands=[(['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_candidate_replay','-o','U:/build/candidate_replay_optimized.vvp',str(bench),'U:/original/compensated/rtl/tdc_time_candicate.v'],'optimized_candidate_replay_compile.log'),
          (['F:/iverilog/bin/vvp.exe','U:/build/candidate_replay_optimized.vvp'],'optimized_candidate_replay.log')]
for args,name in commands:
    with (root/'logs'/name).open('wb') as log:subprocess.run(args,cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
def rows(path):
    with path.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
actual=rows(root/'results/optimized_candidate_replay.csv')
case=root/'results/optimized/baseline/gate_validation'
fields=['time_ps','type','index','code']
assert [[r[k] for k in fields] for r in actual if r['valid']=='1']==[[r[k] for k in fields] for r in rows(case/'candidate.csv')]
conflicts=[int(r['time_ps']) for r in actual if r['conflict']=='1']
assert conflicts==[int(r['time_ps']) for r in rows(case/'errors.csv') if r['kind']=='conflict']
same={name:(case/name).read_bytes()==(root/'results/optimized/compensated/gate_validation'/name).read_bytes() for name in ['raw.csv','candidate.csv','sampled_taps.csv']}
assert all(same.values())
with (case/'raw.csv').open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
result=dict(exact_candidate_replay=True,emitted=sum(r['valid']=='1' for r in actual),conflict_times_ps=conflicts,baseline_compensated_frontend_byte_equal=same,raw_sha256=digest,
    conclusion='新SDF真实四相帧在理想候选RTL中精确重现7018个输出，未产生混合极性冲突。新漏沿不能直接套用旧版本的冲突机制；需检查候选输入形成及相邻去重规则。')
(root/'results/optimized_candidate_replay_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))

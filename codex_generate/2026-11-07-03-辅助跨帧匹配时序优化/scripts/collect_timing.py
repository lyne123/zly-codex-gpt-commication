"""归档成功与失败时序证据，不复制中间大型DCP或改写原报告。"""
from pathlib import Path
import csv,hashlib,json,re,shutil

TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
PREV=ROOT/'codex_generate/2026-11-07-02-辅助下降沿跨帧匹配验证'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

sources=[('F_reference',PREV/'results/implementation_F')]+[(name,WORK/name) for name in [
    'implementation_G','implementation_H','implementation_H2','implementation_physical',
    'implementation_H3','implementation_H3_physical','implementation_closed',
    'implementation_typepair','implementation_fanout','implementation_I',
    'implementation_I_physical','implementation_fifo_reuse2']]
summary=[];manifest={}
for name,source in sources:
    out=TASK/'results/timing'/name;out.mkdir(parents=True,exist_ok=True)
    for p in (source/'after').glob('*'):
        if p.suffix in ['.rpt','.csv']:shutil.copy2(p,out/p.name)
    for filename in ['TIMING_GATE.txt','placement_applied.csv']:
        if (source/filename).exists():shutil.copy2(source/filename,out/filename)
    neg=rows(source/'after/negative_max.csv');hold=rows(source/'after/negative_min.csv')
    core=lambda r:not r['endpoint'].startswith(('u_ila','dbg_hub/'))
    bad=[r for r in neg if core(r)];bad_hold=[r for r in hold if core(r)]
    summary.append(dict(implementation=name,core_setup_negative=len(bad),
        core_setup_WNS_ns=min([float(r['slack_ns']) for r in bad],default=0),
        core_setup_TNS_csv_sum_ns=round(sum(float(r['slack_ns']) for r in bad),3),
        core_hold_negative=len(bad_hold),
        global_setup_negative=len(neg),global_hold_negative=len(hold)))
    for p in source.glob('*.dcp'):
        digest=sha(p);archived=TASK/'implementation'/p.name
        included=archived.exists() and sha(archived)==digest
        manifest[str(p)]=dict(size=p.stat().st_size,sha256=digest,archived=included,
            reason='必要的最终综合或路由DCP已归档' if included else '中间物理实现不重复打包；最终路由DCP单独归档')
for p in WORK.glob('*.log'):
    shutil.copy2(p,TASK/'logs'/p.name)
for p in (WORK/'accepted_bit_export').glob('*.log'):
    shutil.copy2(p,TASK/'logs'/('bit_'+p.name))
for p in (WORK/'baseline_export').glob('*.log'):
    shutil.copy2(p,TASK/'logs'/('baseline_'+p.name))
with (TASK/'results/TIMING_ITERATIONS.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
(TASK/'results/LOCAL_INTERMEDIATE_FILES.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))

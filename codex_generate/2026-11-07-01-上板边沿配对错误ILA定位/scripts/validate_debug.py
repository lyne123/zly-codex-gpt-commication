"""以原FSM为对照检查只读调试逻辑，保留可复现日志。"""
from pathlib import Path
import hashlib,json,re,subprocess
TASK=Path(__file__).resolve().parents[1]
ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_edge_20261107_01'

def main():
    src=json.loads((TASK/'inputs/SOURCE.json').read_text(encoding='utf-8'))
    for name,digest in src['formal_RTL_sha256'].items():
        assert hashlib.sha256((ROOT/'fpga_tdc_v3_cal_rtl'/name).read_bytes()).hexdigest()==digest
    original=(TASK/'inputs/tdc_time_merge.v').read_text(encoding='utf-8')
    reference=WORK/'tdc_time_merge_original.v'
    reference.write_text(original.replace('module tdc_time_merge #(','module tdc_time_merge_original #('),encoding='utf-8')
    commands=[['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_debug_equivalence','-I',str(TASK/'scripts'),'-o',str(WORK/'debug_check.vvp'),str(TASK/'sim/tb_debug_equivalence.sv'),str(TASK/'rtl/tdc_time_merge.v'),str(reference)],['F:/iverilog/bin/vvp.exe',str(WORK/'debug_check.vvp')]]
    logs=[]
    for i,cmd in enumerate(commands):
        p=subprocess.run(cmd,cwd=WORK,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (TASK/'logs'/f'equivalence_{i}.log').write_bytes(p.stdout)
        assert p.returncode==0,p.stdout.decode(errors='replace')
        logs.append(p.stdout.decode(errors='replace'))
    m=re.search(r'DEBUG_EQUIVALENCE_PASS cycles=(\d+) trigger_a=(\d+) trigger_b=(\d+)',logs[-1]);assert m
    result=dict(functional_equivalence=True,cycles=int(m[1]),trigger_a=int(m[2]),trigger_b=int(m[3]),
        formal_RTL_unchanged=True,trigger_source='原error_event_valid/code，未复制正式错误判断',
        limitations='原配对FSM与Debug副本逐拍比较；不代替全TDC、SDF、物理时序或上板触发验收')
    (TASK/'results/RTL_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(logs[-1])
if __name__=='__main__':main()

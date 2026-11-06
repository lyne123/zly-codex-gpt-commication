"""只运行Debug补偿版一次理想RTL验证，与当前上板源版本的冻结3512脉冲结果逐字节比较。"""
from pathlib import Path
import hashlib,json,shutil,subprocess
TASK=Path(__file__).resolve().parents[1]; ROOT=TASK.parents[1]
PREV=ROOT/'codex_generate/2026-11-05-05-四相TDC核心时序优化'
WORK=ROOT/'codex_generate/.vivado_work/tdc_edge_20261107_01/rtl_validation'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    WORK.mkdir(parents=True,exist_ok=True)
    out=WORK/'output_ascii';out.mkdir(exist_ok=True)
    assert not (out/'simulation.log').exists(), '禁止覆盖已完成验证'
    args=['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_tdc','-I',str(PREV/'sim'),'-I',str(TASK/'scripts'),
          '-DAUX_MODE=1','-DFOUR_PHASE_MONITOR','-DCOMPENSATED_RTL',
          '-o',str(WORK/'sim.vvp'),str(PREV/'sim/tb_quick.sv'),str(PREV/'sim/functional_models.v'),
          str(TASK/'sim/tb_debug_equivalence.sv')]+[str(p) for p in sorted((TASK/'rtl').glob('*.v'))]
    with (TASK/'logs/full_rtl_compile.log').open('wb') as f:subprocess.run(args,cwd=WORK,stdout=f,stderr=subprocess.STDOUT,check=True)
    shutil.copy2(PREV/'sim/stimuli/full.txt',WORK/'stimulus.txt')
    assert sha(WORK/'stimulus.txt')==sha(PREV/'sim/stimuli/full.txt')
    with (out/'simulation.log').open('wb') as f:
        subprocess.run(['F:/iverilog/bin/vvp.exe',str(WORK/'sim.vvp'),
            f'+STIMULUS={(WORK/"stimulus.txt").as_posix()}',f'+OUTPUT_DIR={out.as_posix()}',
            '+AUX_INPUT_DELAY_PS=0'],cwd=WORK,stdout=f,stderr=subprocess.STDOUT,check=True)
    shutil.copy2(out/'simulation.log',TASK/'logs/full_rtl_simulation.log')
    assert b'TDC_SIM_DONE' in (out/'simulation.log').read_bytes()
    original=PREV/'results/rtl/compensated/rtl_full'
    checks=[]
    for name in ['raw.csv','candidate.csv','sampled_taps.csv','aux_trace.csv','timestamps.csv',
                 'widths.csv','fifo.csv','errors.csv','error_fifo.csv','anomaly_pipeline_trace.csv']:
        a,b=sha(out/name),sha(original/name)
        checks.append(dict(file=name,debug_sha256=a,production_source_sha256=b,identical=a==b))
    assert all(r['identical'] for r in checks),checks
    import csv
    with (out/'widths.csv').open() as f:n=sum(1 for r in csv.DictReader(f))
    assert n==3512
    result=dict(pass_equivalence=True,valid_widths=n,files=checks,
        comparison='同一冻结3512脉冲激励，Debug理想RTL输出对照05当前源版本冻结结果，10类CSV逐字节一致',
        limitation='不是MAX-SDF或上板测量；本次未重做精度校准',runtime_output=str(out))
    (TASK/'results/FULL_RTL_EQUIVALENCE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FULL_DEBUG_RTL_EQUIVALENCE_PASS pulses=3512 csv_files=10')
if __name__=='__main__':main()

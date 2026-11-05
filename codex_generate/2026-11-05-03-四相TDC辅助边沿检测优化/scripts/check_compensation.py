"""固定使用上一轮8参数做功能等价检查，不重新校准、不宣称新补偿RMS。"""
from pathlib import Path
import csv,hashlib,json,shutil,subprocess

ROOT=Path('W:/');OLD=Path('U:/')

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def run(args,cwd,log):
    with log.open('wb') as f:subprocess.run(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,check=True)

def main():
    work=ROOT/'build/compensation_functional';work.mkdir(exist_ok=True)
    case=ROOT/'results/compensation_functional'
    if case.exists():raise SystemExit('禁止覆盖已保存的补偿功能测试')
    case.mkdir()
    shutil.copyfile(OLD/'results/tdc_skew_calibration.csv',ROOT/'inputs/frozen_compensation.csv')
    params=read(ROOT/'inputs/frozen_compensation.csv');assert len(params)==8
    overrides=['.ENABLE_SKEW_COMP(1)']
    for r in params:
        value=int(r['offset_ps']);literal=("-18'sd"+str(-value)) if value<0 else ("18'sd"+str(value))
        overrides.append(f".{r['polarity'].upper()}_OFFSET_{r['tdl_phase']}_PS({literal})")
    (work/'compensation_parameters.vh').write_text('`define COMPENSATION_PARAMETERS #('+','.join(overrides)+')\n',encoding='ascii')
    args=['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_tdc','-I',str(ROOT/'sim'),'-I',str(work),'-DAUX_MODE=1','-DFOUR_PHASE_MONITOR','-DCOMPENSATED_RTL','-o',str(work/'sim.vvp'),str(ROOT/'sim/tb_quick.sv'),str(ROOT/'sim/functional_models.v')]+[str(p) for p in sorted((ROOT/'rtl').glob('*.v'))]
    run(args,work,work/'compile.log')
    for src,dest in [('local.txt','stimulus.txt'),('local_truth.csv','truth.csv')]:shutil.copyfile(ROOT/'sim/stimuli'/src,case/dest)
    run(['F:/iverilog/bin/vvp.exe',str(work/'sim.vvp'),f'+STIMULUS={case.as_posix()}/stimulus.txt',f'+OUTPUT_DIR={case.as_posix()}', '+AUX_INPUT_DELAY_PS=0'],work,case/'simulation.log')
    assert b'TDC_SIM_DONE' in (case/'simulation.log').read_bytes()
    base=ROOT/'results/rtl_a1_l0_d0_local_r3'
    for name in ['raw.csv','candidate.csv','sampled_taps.csv']:assert (case/name).read_bytes()==(base/name).read_bytes(),name
    offsets={(int(r['sel_index']),int(r['polarity']=='rise')):int(r['offset_ps']) for r in params}
    candidates=read(base/'candidate.csv');normal=read(base/'timestamps.csv');comp=read(case/'timestamps.csv')
    assert len(candidates)==len(normal)==len(comp)==320
    for c,b,a in zip(candidates,normal,comp):
        assert a['time_ps']==b['time_ps'] and a['type']==b['type']
        assert int(a['timestamp_ps'])==(int(b['timestamp_ps'])-offsets[int(c['index']),int(c['type'])])%2048000
    bw=read(base/'widths.csv');cw=read(case/'widths.csv');assert len(bw)==len(cw)==160
    for i,(b,a) in enumerate(zip(bw,cw)):
        r,f=candidates[2*i:2*i+2];assert r['type']=='1' and f['type']=='0'
        assert int(a['width_ps'])==(int(b['width_ps'])-offsets[int(f['index']),0]+offsets[int(r['index']),1])%2048000
    result=dict(pass_all=True,frontend_byte_identical=True,timestamps_checked=320,widths_checked=160,parameter_count=8,parameters_recalculated=False,formal_compensated_rms_deferred=True)
    (case/'FUNCTIONAL_CHECK.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()

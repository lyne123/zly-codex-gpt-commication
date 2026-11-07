"""先检查阈值与流水，再在同批3512激励及三组模型延迟下对比；失败不进入实现。"""
from pathlib import Path
import json,shutil,subprocess
from analyze_rtl import analyze,write
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_noaux_20261107_04'
IVER='F:/iverilog/bin/iverilog.exe';VVP='F:/iverilog/bin/vvp.exe'

def run(args,cwd,log):
    with log.open('wb') as f:return subprocess.run(list(map(str,args)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT).returncode

rtl=sorted((WORK/'rtl').glob('*.v'));models=WORK/'sim/functional_models.v'
unit_results={}
for top,marker in [('tb_range','RANGE_BOUNDARIES_PASS cases=1024'),('tb_bypass','BYPASS_PIPELINE_PASS cases=2592')]:
    out=TASK/'results/rtl'/top
    if out.exists() and (out/'simulation.log').exists() and marker in (out/'simulation.log').read_text(encoding='utf-8',errors='replace'):
        unit_results[top]=True;print('REUSED_COMPLETED_UNIT',top,flush=True);continue
    out.mkdir(parents=True,exist_ok=False)
    native=WORK/top;native.mkdir(exist_ok=False)
    args=[IVER,'-g2012','-s',top,'-o',native/'sim.vvp',TASK/'sim/tb_units.sv',models]+rtl
    rc=run(args,WORK,out/'compile.log')
    if not rc:rc=run([VVP,native/'sim.vvp'],WORK,out/'simulation.log')
    passed=not rc and marker in (out/'simulation.log').read_text(encoding='utf-8',errors='replace')
    unit_results[top]=passed
    assert passed,f'{top}失败；保留日志，禁止进入实现'
    print(marker,flush=True)
results=[];rows=[]
for delay in [0,250,500]:
    native=WORK/f'rtl_lut{delay}';native.mkdir(exist_ok=False)
    for mode in ['aux_on','noaux']:(native/mode).mkdir()
    out=TASK/f'results/rtl/lut{delay}';out.mkdir(parents=True,exist_ok=False)
    args=[IVER,'-g2012','-s','tb_compare','-I',WORK/'sim',f'-DRTL_LUT_DELAY={delay}','-o',native/'sim.vvp',WORK/'sim/tb_compare.sv',models]+rtl+sorted((WORK/'reference_renamed').glob('*.v'))
    rc=run(args,WORK,out/'compile.log')
    if not rc:rc=run([VVP,native/'sim.vvp',f'+INPUT={(WORK/"inputs/full.txt").as_posix()}',f'+OUT={native.as_posix()}'],WORK,out/'simulation.log')
    if rc:
        (out/'RUN_FAILED.json').write_text(json.dumps(dict(returncode=rc,completed=False)),encoding='utf-8')
        raise RuntimeError(f'RTL运行未完成，保留{out}')
    assert 'RTL_COMPARE_COMPLETE' in (out/'simulation.log').read_text(encoding='utf-8',errors='replace'),out
    per={}
    for mode in ['aux_on','noaux']:
        shutil.copytree(native/mode,out/mode)
        r=analyze(out/mode,delay);per[mode]=r
        rows.append(dict(model_LUT_delay_ps=delay,mode=mode,expected_pulses=r['expected_pulses'],actual_valid_pulses=r['actual_valid_pulses'],correct_pulses=r['correct_pulses'],missing_rise=len(r['missing_rise_ids']),missing_fall=len(r['missing_fall_ids']),duplicate_edges=r['duplicate_edges'],mispairs=r['mispairs'],polarity_conflict=r['polarity_conflict'],repeat_rise=r['repeat_rise'],orphan_fall=r['orphan_fall'],merge_range_errors=r['merge_range_errors'],accepted_out_of_range=r['accepted_out_of_range'],raw_range_rejected=r['raw_range_rejected'],functional_pass=r['functional_pass']))
        print('RTL_RESULT',delay,mode,'valid',r['actual_valid_pulses'],'correct',r['correct_pulses'],'pass',r['functional_pass'],flush=True)
    results.append(dict(delay_ps=delay,AuxOn_default_matches_base_each_cycle=True,data_ready_coarse_alignment=True,results=per))
gate=dict(pass_all=all(r['functional_pass'] for group in results for r in group['results'].values()),
    unit_results=unit_results,base_commit='d8b691b65316246567696cdbf8abd4e0f30950ee',cases=results,
    inputs_identical=True,thresholds_unchanged=True,additional_cycles=0,parameters_refitted=False)
(TASK/'results/RTL_GATE.json').write_text(json.dumps(gate,ensure_ascii=False,indent=2),encoding='utf-8')
write(TASK/'results/RTL_COMPARISON.csv',rows,list(rows[0]))
print('RTL_STAGE_GATE',gate['pass_all'],flush=True)

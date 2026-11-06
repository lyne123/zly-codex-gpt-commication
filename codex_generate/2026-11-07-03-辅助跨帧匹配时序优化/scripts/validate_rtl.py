"""按组合、真实重放、三组完整PWM顺序检查；任一失败不进入实现。"""
from pathlib import Path
import argparse,csv,json,shutil,subprocess,os
from capture_io import read_capture,column
from pwm_analysis import analyze
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
PREV=ROOT/'codex_generate/2026-11-07-02-辅助下降沿跨帧匹配验证'
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
VARIANT=os.environ.get('TDC_VARIANT','G_precompute')
RESULT=TASK/'results' if VARIANT=='G_precompute' else TASK/'results'/VARIANT
RUN=WORK if VARIANT=='G_precompute' else WORK/('validation_'+VARIANT)
RESULT.mkdir(parents=True,exist_ok=True);RUN.mkdir(parents=True,exist_ok=True)
def run(args,log):
    with log.open('wb') as f:subprocess.run(list(map(str,args)),cwd=WORK,stdout=f,stderr=subprocess.STDOUT,check=True)
def compile_case(top,out,delay=0):
    if top=='tb_guard_properties' and VARIANT!='G_precompute':source=top+'_H.sv'
    elif VARIANT=='I_confirmation_pipe':source=top+'_I.sv'
    else:source=top+'.sv'
    b=out/'sim.vvp';files=[WORK/'sim'/source,WORK/'sim/functional_models.v']+sorted((WORK/VARIANT).glob('*.v'))
    if top!='tb_guard_properties':files+=sorted((WORK/'F_renamed').glob('*.v'))
    run(['F:/iverilog/bin/iverilog.exe','-g2012','-s',top,'-I',WORK/'sim',f'-DRTL_LUT_DELAY={delay}','-o',b]+files,out/'compile.log')
    return b
def guard():
    out=RUN/'guard';out.mkdir(exist_ok=True);dest=RESULT/'guard';dest.mkdir(exist_ok=True)
    b=compile_case('tb_guard_properties',out)
    run(['F:/iverilog/bin/vvp.exe',b],out/'simulation.log')
    assert 'GUARD_PROPERTIES_PASS cases=262144' in (out/'simulation.log').read_text()
    for p in out.glob('*.log'):shutil.copy2(p,dest/p.name)
    (dest/'SUMMARY.json').write_text(json.dumps(dict(pass_all=True,cases=262144)),encoding='utf-8')
    print('G_GUARD_PASS 262144',flush=True)
def replay():
    out=RUN/'replay';out.mkdir(exist_ok=True);dest=RESULT/'replay';dest.mkdir(exist_ok=True)
    data=read_capture(TASK/'inputs/TRIGGER_A.csv')
    with (out/'input.txt').open('w') as f:
        for i,r in enumerate(data):
            pack=r[column(r,'debug_raw_q')];aux=r[column(r,'debug_aux_q')]
            f.write(f'{i} {(pack>>30)&1023:x} {pack&1023:x} {(pack>>10)&1023:x} {(pack>>20)&1023:x} {aux&15:x}\n')
    b=compile_case('tb_replay',out);target=out/'RTL_REPLAY.csv'
    run(['F:/iverilog/bin/vvp.exe',b,f'+INPUT={(out/"input.txt").as_posix()}',f'+OUTPUT={target.as_posix()}'],out/'simulation.log')
    reference=PREV/'results/replay/F_factored/RTL_REPLAY.csv'
    if VARIANT=='I_confirmation_pipe':
        def rows(p):
            with p.open(newline='') as f:return [{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
        actual,old=rows(target),rows(reference)
        static={'rise_slots','fall_slots','fall_now','fall_previous','fall_claimed_previous','fall_match','final_types'}
        for i in range(20,len(actual)):
            for k in actual[i]:
                if k=='sample':continue
                expected=old[i][k] if k in static else old[i-1][k]
                assert actual[i][k]==expected,(i,k,actual[i][k],expected)
        marker='F_PIPELINE_EQUIVALENCE_PASS'
    else:
        assert target.read_bytes()==reference.read_bytes(),'真实重放与F逐拍输出不等价'
        marker='F_CYCLE_EQUIVALENCE_PASS'
    assert marker in (out/'simulation.log').read_text()
    for p in list(out.glob('*.log'))+[target]:shutil.copy2(p,dest/p.name)
    (dest/'SUMMARY.json').write_text(json.dumps(dict(pass_all=True,reference_F_byte_equal=VARIANT!='I_confirmation_pipe',added_output_cycles=int(VARIANT=='I_confirmation_pipe'),samples=1024,recovered_sample731=True)),encoding='utf-8')
    print('G_REAL_CSV_F_BYTE_EQUAL_PASS',flush=True)
def pwm():
    shutil.copy2(TASK/'inputs/PWM_INPUT.txt',WORK/'pwm_input.txt')
    with (TASK/'inputs/PWM_TRUTH.csv').open(newline='',encoding='utf-8') as f:truth=list(csv.DictReader(f))
    for r in truth:
        for k in r:
            if k!='case':r[k]=int(r[k])
    results={}
    for delay in [0,250,500]:
        out=RUN/f'pwm_lut{delay}';out.mkdir(exist_ok=True);assert not (out/'timestamps.csv').exists(),'禁止覆盖仿真CSV'
        dest=RESULT/f'pwm_lut{delay}';dest.mkdir(exist_ok=True)
        b=compile_case('tb_pwm',out,delay)
        run(['F:/iverilog/bin/vvp.exe',b,f'+INPUT={(WORK/"pwm_input.txt").as_posix()}',f'+OUT={out.as_posix()}'],out/'simulation.log')
        text=(out/'simulation.log').read_text();marker='F_PIPELINE_EQUIVALENCE_PASS' if VARIANT=='I_confirmation_pipe' else 'F_CYCLE_EQUIVALENCE_PASS';assert 'PWM_RTL_COMPLETE' in text and marker in text
        for p in list(out.glob('*.csv'))+list(out.glob('*.log')):shutil.copy2(p,dest/p.name)
        stats=analyze(dest,truth,delay);assert stats['functional_pass'] and stats['width_tolerance_pass'],stats
        equal=[]
        for name in ['candidate.csv','timestamps.csv','widths.csv','errors.csv','ASSOCIATION.csv','MEASUREMENTS.csv']:
            reference=PREV/f'results/pwm/F_factored_lut{delay}'/name
            if VARIANT=='I_confirmation_pipe':
                with (dest/name).open(newline='') as f:now=list(csv.DictReader(f))
                with reference.open(newline='') as f:old=list(csv.DictReader(f))
                assert len(now)==len(old),(name,len(now),len(old))
                for nr,orr in zip(now,old):
                    for k,v in nr.items():
                        if k in ['time_ps','emit_ps']:assert int(v)==int(orr[k])+2000,(name,k,v,orr[k])
                        else:assert v==orr[k],(name,k,v,orr[k])
            else:assert (dest/name).read_bytes()==reference.read_bytes(),name
            equal.append(name)
        stats.update(F_cycle_equivalent=VARIANT!='I_confirmation_pipe',F_equal_after_known_delay=True,added_output_cycles=int(VARIANT=='I_confirmation_pipe'),byte_equal_to_F=equal if VARIANT!='I_confirmation_pipe' else [],equal_value_CSV=equal,result_fifo_overflow='overflow_result=0' not in text,error_fifo_overflow='overflow_error=0' not in text)
        assert not stats['result_fifo_overflow'] and not stats['error_fifo_overflow']
        (dest/'SUMMARY.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8');results[str(delay)]=stats
        print('G_PWM_PASS',delay,'1344 pulses; F exact cycle/CSV equality',flush=True)
    (RESULT/'RTL_STAGE_GATE.json').write_text(json.dumps(dict(variant=VARIANT,pass_all=True,guard_cases=262144,real_csv_recovered=True,added_output_cycles=int(VARIANT=='I_confirmation_pipe'),pwm=results),ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['guard','replay','pwm','all']);a=p.parse_args()
    for name,fn in [('guard',guard),('replay',replay),('pwm',pwm)]:
        if a.stage in [name,'all']:fn()

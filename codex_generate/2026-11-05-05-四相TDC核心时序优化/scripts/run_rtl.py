"""使用冻结3512激励比较旁路/补偿，检查原算术与输出有效时序。"""
from pathlib import Path
import contextlib,csv,hashlib,importlib.util,json,shutil,subprocess

ROOT=Path('W:/');OLD=Path('U:/');PREV=Path('X:/');MOD=2048000
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(args,cwd,log):
    with log.open('wb') as f:subprocess.run(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,check=True)
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    parent=ROOT/'results/rtl';parent.mkdir(exist_ok=True)
    spec=importlib.util.spec_from_file_location('rtl_analysis',PREV/'scripts/quick_rtl.py');ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
    offsets={(int(r['sel_index']),int(r['polarity']=='rise')):int(r['offset_ps']) for r in read(ROOT/'inputs/frozen_compensation.csv')}
    variants={}
    for variant in ['baseline','compensated']:
        work=ROOT/'build'/('rtl_'+variant);work.mkdir(exist_ok=True)
        args=['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_tdc','-I',str(ROOT/'sim'),'-DAUX_MODE=1','-DFOUR_PHASE_MONITOR']
        if variant=='compensated':args+=['-DCOMPENSATED_RTL']
        args+=['-o',str(work/'sim.vvp'),str(ROOT/'sim/tb_quick.sv'),str(ROOT/'sim/functional_models.v')]+[str(p) for p in sorted((ROOT/'rtl').glob('*.v'))]
        run(args,work,work/'compile.log')
        case=parent/variant/'rtl_full'
        if not case.exists():
            case.mkdir(parents=True)
            for src,dst in [('full.txt','stimulus.txt'),('full_truth.csv','truth.csv')]:shutil.copyfile(ROOT/'sim/stimuli'/src,case/dst)
            run(['F:/iverilog/bin/vvp.exe',str(work/'sim.vvp'),f'+STIMULUS={case.as_posix()}/stimulus.txt',f'+OUTPUT_DIR={case.as_posix()}', '+AUX_INPUT_DELAY_PS=0'],work,case/'simulation.log')
        # 已完成的原始仿真只读复核，不覆盖或重复运行。
        assert b'TDC_SIM_DONE' in (case/'simulation.log').read_bytes()
        if variant=='baseline':
            with (case/'analysis.log').open('w',encoding='utf-8') as f,contextlib.redirect_stdout(f):ref.analyze(case,0)
            summary=json.loads((case/'summary.json').read_text())
            assert summary['pass_measurement'] and summary['pass_aux'],'理想RTL事件关联失败'
        variants[variant]=case
        print('RTL_SIM_COMPLETE',variant,len(read(case/'widths.csv')),flush=True)
    b,c=variants['baseline'],variants['compensated']
    for variant,case in variants.items():
        for name in ['raw.csv','candidate.csv','sampled_taps.csv','aux_trace.csv','timestamps.csv','widths.csv','fifo.csv','errors.csv','error_fifo.csv','anomaly_pipeline_trace.csv']:
            assert (case/name).read_bytes()==(Path('Y:/results/rtl')/variant/'rtl_full'/name).read_bytes(),(variant,name)
    print('FULL_RTL_BYTE_EQUIVALENCE_PASS both variants',flush=True)
    for name in ['raw.csv','candidate.csv','sampled_taps.csv','aux_trace.csv']:
        assert (b/name).read_bytes()==(c/name).read_bytes(),name
    assert not read(c/'errors.csv') and not read(c/'error_fifo.csv')
    assert [r['width_ps'] for r in read(c/'widths.csv')]==[r['width_ps'] for r in read(c/'fifo.csv')]
    for name in ['candidate.csv','timestamps.csv','widths.csv','fifo.csv']:
        assert (b/name).read_bytes()==(PREV/'results/rtl_a1_l0_d0_full_r4'/name).read_bytes(),name
    candidates=read(b/'candidate.csv');normal=read(b/'timestamps.csv');comp=read(c/'timestamps.csv');audit=[]
    assert len(candidates)==len(normal)==len(comp)==7024
    for k,(cand,base,adjusted) in enumerate(zip(candidates,normal,comp)):
        index=int(cand['index']);pol=int(cand['type']);code=int(cand['code']);tap=code if pol else 64-code;offset=offsets[index,pol]
        assert adjusted['time_ps']==base['time_ps'] and adjusted['type']==base['type']
        assert int(adjusted['timestamp_ps'])==(int(base['timestamp_ps'])-offset)%MOD
        audit.append(dict(sequence=k,time_ps=cand['time_ps'],sel_index=index,tdl_phase=[90,180,270,0][index],polarity='rise' if pol else 'fall',chosen_code=code,raw_fine_ps=tap*10,mid_ps=(index+1)*500,offset_ps=offset,uncompensated_relative_ps=(index+1)*500-tap*10,compensated_relative_ps=(index+1)*500-tap*10-offset,baseline_timestamp_ps=base['timestamp_ps'],compensated_timestamp_ps=adjusted['timestamp_ps']))
    assert len(read(b/'widths.csv'))==len(read(c/'widths.csv'))==3512
    for i,(base,adjusted) in enumerate(zip(read(b/'widths.csv'),read(c/'widths.csv'))):
        rise,fall=candidates[2*i:2*i+2]
        assert base['time_ps']==adjusted['time_ps']
        assert int(adjusted['width_ps'])==(int(base['width_ps'])+offsets[int(rise['index']),1]-offsets[int(fall['index']),0])%MOD
    write(ROOT/'results/RTL_COMPENSATION_TRACE.csv',audit)
    # 边界测试单独覆盖所有物理相位/极性/有效tap及粗计数回卷。
    unit=ROOT/'build/locate_boundary';unit.mkdir(exist_ok=True)
    run(['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_locate_boundary','-I',str(ROOT/'sim'),'-o',str(unit/'sim.vvp'),str(ROOT/'sim/tb_locate_boundary.sv'),str(ROOT/'rtl/tdc_time_locate.v')],unit,unit/'compile.log')
    run(['F:/iverilog/bin/vvp.exe',str(unit/'sim.vvp')],unit,ROOT/'logs/locate_boundary.log')
    inputs=read(ROOT/'results/LOCATE_BOUNDARY_INPUT.csv');outputs=read(ROOT/'results/LOCATE_BOUNDARY_OUTPUT.csv');assert len(inputs)==len(outputs)
    wrap_low=wrap_high=0;seen=set()
    for a,z in zip(inputs,outputs):
        coarse,idx,pol,code=[int(a[k]) for k in ['coarse','index','polarity','code']];fine=(code if pol else 64-code)*10
        raw=((coarse+1)%1024)*2000+(idx+1)*500-fine;expected=(raw-offsets[idx,pol])%MOD
        assert int(z['baseline'])==raw%MOD and int(z['compensated'])==expected and int(z['polarity'])==pol,(a,z,expected)
        assert int(z['time_ps'])-int(a['time_ps'])==8000
        wrap_low+=raw-offsets[idx,pol]<0;wrap_high+=raw>=MOD;seen.add((idx,pol,code))
    assert len(seen)==4*2*65 and wrap_low and wrap_high
    result=dict(rtl_pass=True,expected_pulses=3512,actual_pulses=3512,valid_edges=7024,frontend_byte_identical=True,baseline_matches_verified_commit=True,timestamp_checks=7024,width_checks=3512,locate_boundary_samples=len(inputs),phase_polarity_tap_combinations=len(seen),negative_wrap_cases=wrap_low,positive_wrap_cases=wrap_high,parameters_recalculated=False,rtl_sha256={p.name:sha(p) for p in (ROOT/'rtl').glob('*.v')})
    (ROOT/'results/RTL_STAGE_GATE.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

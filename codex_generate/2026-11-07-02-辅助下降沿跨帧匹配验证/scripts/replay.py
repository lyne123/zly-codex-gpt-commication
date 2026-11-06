"""用实际RTL重放冻结的1024点，逐拍核对A并比较B/C/D；原始CSV只读。"""
from pathlib import Path
import csv,hashlib,json,shutil,subprocess,sys,os
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02'
from capture_io import read_capture,column
def run(args,log):
    with log.open('wb') as f:subprocess.run(list(map(str,args)),cwd=WORK,stdout=f,stderr=subprocess.STDOUT,check=True)
def read(p):
    with p.open(newline='') as f:return [{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
def main():
    data=read_capture(TASK/'inputs/TRIGGER_A.csv');assert len(data)==1024
    assert data[728][column(data[728],'debug_aux_q')]>>11&15==8
    assert data[728][column(data[728],'debug_aux_q')]>>27&15==0
    with (WORK/'replay_input.txt').open('w') as f:
        for i,r in enumerate(data):
            pack=r[column(r,'debug_raw_q')];aux=r[column(r,'debug_aux_q')]
            f.write(f'{i} {(pack>>30)&1023:x} {pack&1023:x} {(pack>>10)&1023:x} {(pack>>20)&1023:x} {aux&15:x}\n')
    shutil.copytree(TASK/'sim',WORK/'sim',dirs_exist_ok=True)
    outputs={};stats={}
    for variant in os.environ.get('TDC_COMPARE_VARIANTS','A_baseline B_previous C_delay_fall D_fallback').split():
        out=TASK/'results/replay'/variant;out.mkdir(parents=True,exist_ok=True)
        binary=WORK/(variant+'.vvp');csv_file=WORK/(variant+'_replay.csv')
        run(['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_replay','-I',WORK/'sim','-o',binary,WORK/'sim/tb_replay.sv',WORK/'sim/functional_models.v']+sorted((WORK/variant).glob('*.v')),out/'compile.log')
        run(['F:/iverilog/bin/vvp.exe',binary,f'+INPUT={(WORK/"replay_input.txt").as_posix()}',f'+OUTPUT={csv_file.as_posix()}'],out/'simulation.log')
        assert b'REAL_CSV_RTL_REPLAY_COMPLETE' in (out/'simulation.log').read_bytes()
        rows=read(csv_file);assert len(rows)==1024;outputs[variant]=rows
        shutil.copy2(csv_file,out/'RTL_REPLAY.csv')
        emitted=[(r['sample'],r['edge_type'],r['index'],r['code']) for r in rows if r['edge_valid'] and 20<=r['sample']<1000]
        stats[variant]=dict(timestamp_rises=sum(r['timestamp_valid'] and r['timestamp_type'] for r in rows),
            timestamp_falls=sum(r['timestamp_valid'] and not r['timestamp_type'] for r in rows),
            widths=sum(r['width_valid'] for r in rows),double_rise=sum(r['error_valid'] and r['error_code']==1 for r in rows),
            orphan_fall=sum(r['error_valid'] and r['error_code']==2 for r in rows),conflicts=sum(r['conflict'] for r in rows),
            repeated_candidates=sum(r['repeat_error'] for r in rows),emitted=emitted,
            multi_phase_frames=sum(r['sync_mask'].bit_count()>1 for r in rows))
    baseline=outputs.get('A_baseline') or read(TASK/'results/replay/A_baseline/RTL_REPLAY.csv');checks=0
    for i,(r,o) in enumerate(zip(data,baseline)):
        if i<20:continue
        aux=r[column(r,'debug_aux_q')];pipe=r[column(r,'debug_pipeline_q')];ctrl=r[column(r,'debug_control_q')]
        expected=dict(rise_slots=(aux>>7)&15,fall_slots=(aux>>11)&15,fall_now=(aux>>19)&15,fall_previous=(aux>>27)&15,
            fall_claimed_previous=(aux>>35)&15,fall_match=(aux>>51)&15,final_types=(pipe>>29)&255,sync_mask=pipe&15,
            edge_valid=(pipe>>23)&1,conflict=(pipe>>25)&1,repeat_error=(pipe>>26)&1,
            timestamp_valid=(ctrl>>12)&1,error_valid=(ctrl>>2)&1)
        if expected['edge_valid']:expected.update(edge_type=(pipe>>24)&1,index=(pipe>>13)&3,code=(pipe>>15)&255)
        if expected['timestamp_valid']:expected['timestamp_type']=(ctrl>>13)&1
        if expected['error_valid']:expected['error_code']=(ctrl>>3)&15
        for k,v in expected.items():assert o[k]==v,(i,k,o[k],v);checks+=1
    prior=TASK/'results/REPLAY_COMPARISON.json'
    result=json.loads(prior.read_text(encoding='utf-8')) if prior.exists() else dict(variants={})
    result.update(real_csv_RTL_equivalent=True,checks=checks,scope='从已观测有序采样/相位包边界重放，不冒充物理TDL传播复现')
    base_events={r['sample']:(r['edge_type'],r['index'],r['code']) for r in baseline if r['edge_valid']}
    for variant,s in stats.items():
        ev=s.pop('emitted');s['changed_existing_choices']=sum(base_events.get(t)!=(typ,idx,code) for t,typ,idx,code in ev if t in base_events)
        s['lost_baseline_events']=sum(not outputs[variant][t]['edge_valid'] for t in base_events if 20<=t<1000)
        result['variants'][variant]=s
    (TASK/'results/REPLAY_COMPARISON.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

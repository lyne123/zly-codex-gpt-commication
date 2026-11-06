"""相同激励比较四方案；理想/传输延迟模型仅用于功能压力，不冒充器件SDF。"""
from pathlib import Path
from collections import Counter
import bisect,csv,json,math,shutil,statistics,subprocess,os
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02';MOD=2048000
OFFSETS=[36011,35742,35756,36081]
def read(p):
    with p.open(newline='') as f:return [{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
def run(args,log):
    with log.open('wb') as f:subprocess.run(list(map(str,args)),cwd=WORK,stdout=f,stderr=subprocess.STDOUT,check=True)
def prepare_stimulus():
    truth=[];t=2000000
    cases=['10M_50','20M_50','20M_5','20M_95','10M_20M_switch','adjacent_2ns','phase_boundary']
    for case in cases:
        for phase in [0,1,499,500,501,999,1000,1001,1499,1500,1501,1999]:
            t=((t+1999)//2000)*2000+phase+200000
            for n in range(16):
                period,width={'10M_50':(100000,50000),'20M_50':(50000,25000),'20M_5':(50000,2500),
                    '20M_95':(50000,47500),'adjacent_2ns':(4000,2000),'phase_boundary':(50000,[2499,2500,2501][n%3]),
                    '10M_20M_switch':((100000,50000) if n%2==0 else (50000,25000))}[case]
                truth.append(dict(id=len(truth),case=case,rise_ps=t,fall_ps=t+width,width_ps=width,period_ps=period,phase=phase));t+=period
    with (WORK/'pwm_input.txt').open('w') as f:
        for r in truth:f.write(f"{r['id']} {r['rise_ps']} {r['fall_ps']}\n")
    with (TASK/'inputs/PWM_TRUTH.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(truth[0]));w.writeheader();w.writerows(truth)
    shutil.copy2(WORK/'pwm_input.txt',TASK/'inputs/PWM_INPUT.txt')
    return truth
def analyze(case,truth,delay):
    ts=read(case/'timestamps.csv');widths=read(case/'widths.csv');cand={r['time_ps']:r for r in read(case/'candidate.csv')}
    epoch=read(case/'epoch.csv')[0]['epoch_ps'];assoc=[];bad=0;counts={0:Counter(),1:Counter()}
    bytype={p:sorted((r['rise_ps' if p else 'fall_ps'],r['id']) for r in truth) for p in [0,1]}
    for r in ts:
        c=cand[r['time_ps']-10000];offset=OFFSETS[c['index']]
        wrapped=(r['timestamp_ps']+offset-32000-3*delay+epoch)%MOD
        estimate=wrapped+round((r['time_ps']-40000-wrapped)/MOD)*MOD
        options=bytype[r['type']];times=[x[0] for x in options];j=bisect.bisect_left(times,estimate)
        near=[k for k in [j-1,j] if 0<=k<len(options)];k=min(near,key=lambda k:abs(options[k][0]-estimate))
        true,identity=options[k];residual=estimate-true;bad+=abs(residual)>20
        counts[r['type']][identity]+=1;assoc.append(dict(id=identity,type=r['type'],residual_ps=residual,emit_ps=r['time_ps']))
    pending=None;pairs=[]
    for e in assoc:
        if e['type']:pending=e
        elif pending is not None:pairs.append((pending,e));pending=None
    assert len(pairs)==len(widths),(case,len(pairs),len(widths))
    measured=[]
    for (a,b),w in zip(pairs,widths):
        measured.append(dict(rise_id=a['id'],fall_id=b['id'],width_ps=w['width_ps'],error_ps=w['width_ps']-truth[b['id']]['width_ps']))
    missing_r=[r['id'] for r in truth if not counts[1][r['id']]];missing_f=[r['id'] for r in truth if not counts[0][r['id']]]
    errors=Counter(r['code'] for r in read(case/'errors.csv'));duplicate=sum(max(0,n-1) for c in counts.values() for n in c.values())
    stats=dict(pulses=len(truth),rises=len(ts)-sum(r['type']==0 for r in ts),falls=sum(r['type']==0 for r in ts),
        missing_rise=len(missing_r),missing_fall=len(missing_f),duplicate_edges=duplicate,
        mismatched_pairs=sum(x['rise_id']!=x['fall_id'] for x in measured),double_rise=errors[1],orphan_fall=errors[2],
        range_error=errors[3],association_residual_over_20ps=bad,max_abs_width_error_ps=max((abs(x['error_ps']) for x in measured),default=None),
        missing_by_case={name:dict(rise=sum(truth[i]['case']==name for i in missing_r),fall=sum(truth[i]['case']==name for i in missing_f)) for name in dict.fromkeys(r['case'] for r in truth)})
    stats['functional_pass']=not any([stats[k] for k in ['missing_rise','missing_fall','duplicate_edges','mismatched_pairs','double_rise','orphan_fall','range_error','association_residual_over_20ps']])
    stats['width_tolerance_pass']=stats['max_abs_width_error_ps'] is not None and stats['max_abs_width_error_ps']<=500
    for name,rows in [('ASSOCIATION.csv',assoc),('MEASUREMENTS.csv',measured)]:
        if rows:
            with (case/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return stats
def main():
    truth=prepare_stimulus();shutil.copytree(TASK/'sim',WORK/'sim',dirs_exist_ok=True)
    summary_file=TASK/'results/PWM_COMPARISON.json'
    results=json.loads(summary_file.read_text()) if summary_file.exists() else {}
    for delay in [0,250,500]:
        for variant in os.environ.get('TDC_COMPARE_VARIANTS','A_baseline B_previous C_delay_fall D_fallback').split():
            label=f'{variant}_lut{delay}';case=TASK/'results/pwm'/label;case.mkdir(parents=True,exist_ok=True)
            out=WORK/label;out.mkdir(exist_ok=True);assert not (out/'timestamps.csv').exists(),'禁止覆盖既有仿真'
            binary=out/'sim.vvp'
            run(['F:/iverilog/bin/iverilog.exe','-g2012','-s','tb_pwm','-I',WORK/'sim',f'-DRTL_LUT_DELAY={delay}','-o',binary,WORK/'sim/tb_pwm.sv',WORK/'sim/functional_models.v']+sorted((WORK/variant).glob('*.v')),case/'compile.log')
            run(['F:/iverilog/bin/vvp.exe',binary,f'+INPUT={(WORK/"pwm_input.txt").as_posix()}',f'+OUT={out.as_posix()}'],case/'simulation.log')
            log=(case/'simulation.log').read_text(errors='replace');assert 'PWM_RTL_COMPLETE' in log and 'FATAL:' not in log
            for p in out.glob('*.csv'):shutil.copy2(p,case/p.name)
            stats=analyze(case,truth,delay);stats['result_fifo_overflow']='overflow_result=0' not in log;stats['error_fifo_overflow']='overflow_error=0' not in log
            results[label]=stats;(case/'SUMMARY.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
            print(label,json.dumps({k:v for k,v in stats.items() if k!='missing_by_case'}),flush=True)
    (TASK/'results/PWM_COMPARISON.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
if __name__=='__main__':main()

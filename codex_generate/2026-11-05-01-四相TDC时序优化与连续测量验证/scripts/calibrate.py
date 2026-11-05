"""以独立校准输入和实际实现建立偏移；RTL校准仅供事件关联。"""
from pathlib import Path
import argparse
import bisect
import csv
import json
import statistics
from collections import defaultdict
import legacy_experiment as e

ROOT=Path(__file__).resolve().parents[1]

def run(phase,variant,level,promote=False):
    case=ROOT/'results'/phase/variant/f'{level}_calibration'
    _,truth=e.load_case(case)
    epoch=int(e.read_csv(case/'clock_epoch.csv')[0]['epoch_ps'])
    times={p:[r['rise_ps' if p else 'fall_ps'] for r in truth] for p in (0,1)}
    raw=e.numeric(case/'raw.csv');candidates=e.numeric(case/'candidate.csv');timestamps=e.numeric(case/'timestamps.csv')
    assert len(candidates)==len(timestamps)==1600
    paramfile=ROOT/'inputs/old_tdc_skew_calibration.csv' if phase=='original' else ROOT/'results/tdc_skew_calibration.csv'
    applied={(int(r['sel_index']),int(r['polarity']=='rise')):int(r['offset_ps']) for r in e.read_csv(paramfile)} if variant=='compensated' else {}
    by_time={r['time_ps']:r for r in raw}
    groups=defaultdict(list);observations=[];latencies=defaultdict(list)
    for r in raw:
        for i in range(4):
            if not r['mask']&(1<<i):continue
            pol=(r['polarity']>>(2*i))&3;assert pol in (2,3);p=int(pol==3)
            k=bisect.bisect_right(times[p],r['time_ps'])-1;assert k>=0
            true=times[p][k];code=(r['codes']>>(8*i))&255;tap=code if p else 64-code
            measured=(((r['coarse']+6)%1024)*2000+(i+1)*500-tap*10)%e.MODULO
            error=e.circular(measured-(true-epoch)%e.MODULO)
            groups[i,p].append(error)
            observations.append(dict(sel_index=i,phase=e.PHASES[i],polarity=p,pulse_id=k,time_ps=r['time_ps'],true_time_ps=true,code=code,phase_ps=(true-epoch)%2000,error_ps=error))
    for c,t in zip(candidates,timestamps):
        assert c['type']==t['type'] and t['time_ps']-c['time_ps']==10000
        tap=c['code'] if c['type'] else 64-c['code']
        expected=(((c['coarse']+1)%1024)*2000+(c['index']+1)*500-tap*10-applied.get((c['index'],c['type']),0))%e.MODULO
        assert expected==t['timestamp_ps'],'时间戳公式/控制对齐不成立'
        f=by_time.get(c['time_ps']-10000)
        assert f is not None and f['mask']&(1<<c['index']) and ((f['codes']>>(8*c['index']))&255)==c['code']
        k=bisect.bisect_right(times[c['type']],c['time_ps'])-1
        latencies[c['index'],c['type']].append(c['time_ps']-times[c['type']][k])
    params=[]
    for i in range(4):
        for p in (1,0):
            v=groups[i,p];assert len(v)>=20
            params.append(dict(sel_index=i,tdl_phase=e.PHASES[i],polarity='rise' if p else 'fall',offset_ps=round(statistics.mean(v)),**e.stats(v)))
    out=ROOT/'results/calibration'/phase/variant/level;out.mkdir(parents=True,exist_ok=True)
    e.write_csv(out/'fitted_parameters.csv',params);e.write_csv(out/'observations.csv',observations)
    coverage=defaultdict(list)
    for r in observations:coverage[r['sel_index'],r['polarity'],r['phase_ps']].append(r['error_ps'])
    e.write_csv(out/'phase_coverage.csv',(dict(sel_index=i,type=p,phase_ps=phase,**e.stats(v)) for (i,p,phase),v in sorted(coverage.items())))
    # 事件关联延迟独立来自校准集；主验证集不参与拟合。
    used=[dict(r,offset_ps=applied[(r['sel_index'],int(r['polarity']=='rise'))]) for r in params] if applied else params
    metadata=dict(status='POST_ROUTE_SDF_CALIBRATION' if level=='gate' else 'RTL_ASSOCIATION_ONLY_NOT_PHYSICAL_CALIBRATION',epoch_ps=epoch,
        parameters=used,fitted_parameters=params,candidate_latency={f'{i},{p}':statistics.median(v) for (i,p),v in latencies.items()},
        source_case=str(case.relative_to(ROOT)),input_sha256=e.sha(case/'input_sha256.json'),source_stimulus_sha256=e.sha(case/'stimulus.txt'),
        fitted_matches_applied=all(r['offset_ps']==applied.get((r['sel_index'],int(r['polarity']=='rise')),r['offset_ps']) for r in params))
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    if promote:
        assert phase=='optimized' and variant=='baseline' and level=='gate'
        assert not (ROOT/'results/tdc_skew_calibration.csv').exists(),'拒绝覆盖已冻结参数'
        e.write_csv(ROOT/'results/tdc_skew_calibration.csv',params)
        generics=['ENABLE_SKEW_COMP=1']+[f"{r['polarity'].upper()}_OFFSET_{r['tdl_phase']}_PS={r['offset_ps']}" for r in params]
        (ROOT/'results/calibration_params.tcl').write_text('# 来自本次冻结优化Baseline的独立SDF校准，单位ps。\nset compensation_generics {'+' '.join(generics)+'}\n',encoding='utf-8')
    print(json.dumps(dict(case=str(case),parameters=[(r['tdl_phase'],r['polarity'],r['offset_ps']) for r in params],fitted_matches_applied=metadata['fitted_matches_applied']),ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['original','optimized']);p.add_argument('variant',choices=['baseline','compensated']);p.add_argument('level',choices=['rtl','gate']);p.add_argument('--promote',action='store_true');a=p.parse_args();run(a.phase,a.variant,a.level,a.promote)

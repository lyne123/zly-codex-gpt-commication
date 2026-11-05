"""由实际D_dly/C_dly记录核对四相覆盖及关键事件归属，不调整测量或补偿。"""
from pathlib import Path
from collections import Counter
import bisect,csv,json,statistics

ROOT=Path('W:/')
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    case=ROOT/'results/baseline/gate_local'
    truth=read(case/'truth.csv');changes=read(case/'meta_changes.csv');captures=read(case/'meta_capture.csv')
    expected=sorted((int(r['rise_ps' if p else 'fall_ps']),int(r['source_event_id']),p) for r in truth for p in [0,1])
    times={p:[t for t,i,pol in expected if pol==p] for p in [0,1]}
    delays={};routes=[];phase_clocks={}
    for phase in [0,90,180,270]:
        clocks=[int(r['time_ps']) for r in captures if int(r['phase'])==phase]
        assert clocks;phase_clocks[phase]=clocks
        for p in [0,1]:
            edges=[int(r['time_ps']) for r in changes if r['signal']==f'p{phase}_D_dly' and r['value']==str(p)]
            isolated=[]
            for t in edges:
                eligible=[x for x in times[p] if 0<=t-x<=10000]
                if len(eligible)==1:isolated.append(t-eligible[0])
            assert isolated,(phase,p)
            delay=statistics.median(isolated);assert all(x==delay for x in isolated),(phase,p,isolated)
            delays[phase,p]=int(delay)
            routes.append(dict(phase=phase,polarity=p,input_to_D_dly_ps=int(delay),isolated_edges_used=len(isolated),effective_capture_phase_ps=(clocks[0]-int(delay))%2000))
    gaps=[]
    for p in [0,1]:
        effective={ph:(phase_clocks[ph][0]-delays[ph,p])%2000 for ph in [0,90,180,270]}
        spacing=[(effective[b]-effective[a])%2000 for a,b in [(0,90),(90,180),(180,270),(270,0)]]
        assert sum(spacing)==2000,('物理采样顺序不符合有序帧',p,effective)
        gaps.append(dict(polarity=p,effective_sample_phases=effective,gaps_ps=spacing,maximum_gap_ps=max(spacing),D_dly_path_skew_ps=max(delays[ph,p] for ph in effective)-min(delays[ph,p] for ph in effective)))
    byid={int(r['source_event_id']):r for r in truth};coverage=[]
    for falling,rising in [(2917,2918),(2983,2984),(3049,3050)]:
        fall=int(byid[falling]['fall_ps']);rise=int(byid[rising]['rise_ps'])
        for phase in [0,90,180,270]:
            lo=fall+delays[phase,0];hi=rise+delays[phase,1]
            hit=[r for r in captures if int(r['phase'])==phase and lo<=int(r['time_ps'])<hi]
            assert all(r['D_dly']=='0' for r in hit)
            coverage.append(dict(fall_source_id=falling,rise_source_id=rising,phase=phase,D_low_start_ps=lo,D_low_end_ps=hi,low_samples=len(hit),capture_times_ps=';'.join(r['time_ps'] for r in hit)))
        assert sum(r['low_samples'] for r in coverage if r['fall_source_id']==falling)>0
    observed=[]
    for row in read(case/'aux_events.csv'):
        for slot in range(4):
            for p,key in [(1,'rise_slots'),(0,'fall_slots')]:
                if (int(row[key])>>slot)&1:observed.append(dict(emit_ps=int(row['time_ps']),slot=slot,polarity=p))
    assert len(observed)==len(expected)==320
    ownership=[]
    for obs,(true,pid,p) in zip(observed,expected):
        assert obs['polarity']==p,('辅助事件顺序或极性错误',obs,pid)
        if not any(lo<=true<=hi for lo,hi in [(238600000,238900000),(241900000,242200000),(245200000,245500000)]):continue
        phase=[90,180,270,0][obs['slot']];arrival=true+delays[phase,p]
        clocks=phase_clocks[phase];at=bisect.bisect_left(clocks,arrival)
        assert at<len(clocks)
        capture=clocks[at];residual=capture-arrival
        assert residual<=max(g['maximum_gap_ps'] for g in gaps)+30,(pid,p,phase,residual)
        state=next(r for r in captures if int(r['phase'])==phase and int(r['time_ps'])==capture)
        assert state['D_dly']==str(p),(pid,p,state)
        ownership.append(dict(source_event_id=pid,polarity=p,truth_edge_ps=true,winning_phase=phase,winning_D_arrival_ps=arrival,meta_capture_clock_ps=capture,capture_D=state['D_dly'],aux_emit_ps=obs['emit_ps'],capture_to_aux_emit_ps=obs['emit_ps']-capture))
    latency={ph:{r['capture_to_aux_emit_ps'] for r in ownership if r['winning_phase']==ph} for ph in [0,90,180,270]}
    assert all(len(v)<=1 for v in latency.values()),('事件关联出现可变整拍延迟',latency)
    write(ROOT/'results/AUX_PHYSICAL_INPUT_DELAYS.csv',routes)
    write(ROOT/'results/SIX_EVENT_PHASE_COVERAGE.csv',coverage)
    write(ROOT/'results/SDF_AUX_EVENT_OWNERSHIP.csv',ownership)
    result=dict(pass_all=True,events_checked=320,target_pairs_checked=3,physical_gap_review=gaps,fixed_capture_to_emit_latency_ps={str(ph):list(v) for ph,v in latency.items()},not_compensation_calibration=True)
    (ROOT/'results/SDF_CAPTURE_REVIEW.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

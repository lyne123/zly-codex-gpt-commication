"""沿用冻结的理想RTL关联公式，保留所有漏沿/冲突/错误，不拟合新参数。"""
from pathlib import Path
from collections import Counter
import csv,json,bisect,statistics
TASK=Path(__file__).resolve().parents[1];MOD=2048000
OFFSETS=[36011,35742,35756,36081]

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows,fields):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def analyze(case,delay):
    truth=read(TASK/'inputs/full_truth.csv');byid={int(r['pulse_id']):r for r in truth};n=len(truth)
    options={p:sorted((int(r['rise_ps' if p else 'fall_ps']),int(r['pulse_id'])) for r in truth) for p in [0,1]}
    times={p:[t for t,i in options[p]] for p in [0,1]}
    ts=read(case/'timestamps.csv');cand={int(r['time_ps']):r for r in read(case/'candidate.csv')}
    epoch=int(read(case/'epoch.csv')[0]['epoch_ps']);edges=[];faults=[]
    for row,t in enumerate(ts):
        emit=int(t['time_ps']);pol=int(t['type']);value=int(t['timestamp_ps']);c=cand.get(emit-10000)
        e=dict(row=row,event_id='',status='NO_CANDIDATE',polarity=pol,emit_ps=emit,timestamp_ps=value,residual_ps='')
        if c:
            idx=int(c['index']);code=int(c['code']);coarse=int(c['coarse'])
            # 32000及3级LUT传输项逐字沿用上一轮理想RTL公式，不使用SDF发射偏移。
            wrapped=(value+OFFSETS[idx]-32000-3*delay+epoch)%MOD
            estimate=wrapped+round((emit-40000-wrapped)/MOD)*MOD
            j=bisect.bisect_left(times[pol],estimate);near=[k for k in [j-1,j] if 0<=k<len(times[pol])]
            k=min(near,key=lambda k:abs(times[pol][k]-estimate));true,pid=options[pol][k]
            expected=((((coarse+1)%1024)*2000+(idx+1)*500-(code if pol else 64-code)*10)-OFFSETS[idx])%MOD
            status='MATCHED' if abs(estimate-true)<=20 else 'ASSOCIATION_ERROR'
            if expected!=value:status='ARITHMETIC_ERROR'
            e.update(event_id=pid,status=status,residual_ps=estimate-true,index=idx,code=code)
        if e['status']!='MATCHED':faults.append(dict(row=row,kind=e['status']))
        edges.append(e)
    counts={p:Counter(e['event_id'] for e in edges if e['polarity']==p and e['status']=='MATCHED') for p in [0,1]}
    pending=None;pairs={};pair_faults=[]
    for e in edges:
        if e['status']!='MATCHED':continue
        if e['polarity']:
            if pending:pair_faults.append(dict(kind='repeat_rise',event_id=e['event_id']))
            pending=e
        elif pending:pairs[e['emit_ps']+6000]=(pending,e);pending=None
        else:pair_faults.append(dict(kind='orphan_fall',event_id=e['event_id']))
    widths=read(case/'widths.csv');measure=[]
    for row,w in enumerate(widths):
        value=int(w['width_ps']);pair=pairs.get(int(w['time_ps']));r=dict(row=row,status='UNMATCHED',rise_id='',fall_id='',width_ps=value,error_ps='',case='')
        if pair:
            a,b=pair;pid=b['event_id'];t=byid[pid];status='MATCHED' if a['event_id']==pid else 'MISPAIR'
            if value!=(b['timestamp_ps']-a['timestamp_ps'])%MOD:status='ARITHMETIC_ERROR'
            r.update(status=status,rise_id=a['event_id'],fall_id=pid,error_ps=value-int(t['true_width_ps']),case=t['case'])
        measure.append(r)
    if pending:pair_faults.append(dict(kind='unclosed_rise',event_id=pending['event_id']))
    good=[r for r in measure if r['status']=='MATCHED'];matched=Counter(r['fall_id'] for r in good)
    errors=read(case/'errors.csv');codes=Counter(int(r['code']) for r in errors);counter=json.loads((case/'COUNTERS.json').read_text())
    fifo=read(case/'fifo.csv');ef=read(case/'error_fifo.csv')
    fifo_equal=[r['width_ps'] for r in fifo]==[r['width_ps'] for r in widths]
    error_fifo_equal=[r['code'] for r in ef]==[r['code'] for r in errors]
    missing={p:sorted(set(byid)-set(counts[p])) for p in [0,1]}
    duplicate=sum(v-1 for c in counts.values() for v in c.values() if v>1)
    statistics_by_case={}
    for name in dict.fromkeys(r['case'] for r in truth):
        ids={int(r['pulse_id']) for r in truth if r['case']==name};rr=[r for r in good if r['fall_id'] in ids]
        statistics_by_case[name]=dict(expected=len(ids),correct_pulses=len({r['fall_id'] for r in rr}),
            missing_rise=len(ids&set(missing[1])),missing_fall=len(ids&set(missing[0])),
            duplicate_edges=sum(max(v-1,0) for c in counts.values() for i,v in c.items() if i in ids),
            max_abs_width_error_ps=max((abs(r['error_ps']) for r in rr),default=None))
    maxerr=max((abs(r['error_ps']) for r in good),default=None)
    passed=(len(ts)==2*n and len(good)==len(matched)==n and not missing[0] and not missing[1] and not duplicate and not faults and not pair_faults and not errors and
        not counter['polarity_conflict'] and not counter['candidate_repeat'] and not counter['accepted_out_of_range'] and not counter['FIFO_overflow_seen'] and fifo_equal and error_fifo_equal and len(fifo)==n and maxerr is not None and maxerr<=500)
    result=dict(expected_pulses=n,timestamps=len(ts),rises=sum(e['polarity']==1 for e in edges),falls=sum(e['polarity']==0 for e in edges),actual_valid_pulses=len(widths),correct_pulses=len(matched),
        missing_rise_ids=missing[1],missing_fall_ids=missing[0],duplicate_edges=duplicate,mispairs=sum(r['status']=='MISPAIR' for r in measure),
        repeat_rise=codes[1],orphan_fall=codes[2],merge_range_errors=codes[3],**counter,
        FIFO_sequence_equal=fifo_equal,error_FIFO_sequence_equal=error_fifo_equal,
        association_faults=faults,pair_faults=pair_faults,max_abs_width_error_ps=maxerr,by_case=statistics_by_case,
        functional_pass=passed,NoAux_vs_AuxOn_extra_cycles=0,parameters_refitted=False,outliers_removed=False)
    write(case/'EDGE_RESULTS.csv',edges,['row','event_id','status','polarity','emit_ps','timestamp_ps','residual_ps','index','code'])
    write(case/'MEASUREMENTS.csv',measure,['row','status','rise_id','fall_id','width_ps','error_ps','case'])
    (case/'SUMMARY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

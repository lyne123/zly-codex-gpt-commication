"""逐字复用上一轮脉宽/事件ID分析函数，不重新拟合参数。"""
import csv,bisect
from collections import Counter
MOD=2048000
OFFSETS=[36011,35742,35756,36081]
def read(p):
    with p.open(newline='') as f:return [{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
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

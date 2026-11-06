"""按预先隔离的四脉冲短段检查SDF顺序、计数、宽度和FIFO序列；不重拟合参数。"""
from pathlib import Path
from collections import Counter
import csv,json
TASK=Path(__file__).resolve().parents[1]
def read(p):
    with p.open(newline='') as f:return [{k:int(v) for k,v in r.items()} for r in csv.DictReader(f)]
with (TASK/'inputs/SDF_TRUTH.csv').open(newline='',encoding='utf-8') as f:truth=list(csv.DictReader(f))
for r in truth:
    for k in r:
        if k!='case':r[k]=int(r[k])
groups=[truth[i:i+4] for i in range(0,len(truth),4)]
out=TASK/'results/sdf';ts=read(out/'timestamps.csv');width=read(out/'widths.csv');errors=read(out/'errors.csv');fifo=read(out/'fifo.csv')
assigned=[[] for g in groups];wgroup=[[] for g in groups];unexpected=[]
for rows,dest in [(ts,assigned),(width,wgroup)]:
    for r in rows:
        matches=[i for i,g in enumerate(groups) if g[0]['rise_ps']+20000<=r['time_ps']<=g[-1]['fall_ps']+100000]
        if len(matches)==1:dest[matches[0]].append(r)
        else:unexpected.append(r)
details=[];patterns=0;missing_r=0;missing_f=0;extra=0;maxerr=0;badwidth=0
for g,ev,ws in zip(groups,assigned,wgroup):
    pattern=[r['type'] for r in ev];rises=sum(pattern);falls=len(ev)-rises
    patterns+=pattern!=[1,0]*len(g);missing_r+=max(0,len(g)-rises);missing_f+=max(0,len(g)-falls)
    extra+=max(0,rises-len(g))+max(0,falls-len(g));we=[]
    for w,t in zip(ws,g):we.append(w['width_ps']-t['width_ps'])
    if we:maxerr=max(maxerr,max(abs(x) for x in we))
    badwidth+=len(ws)!=len(g) or any(abs(x)>1000 for x in we)
    details.append(dict(case=g[0]['case'],phase=g[0]['phase'],pulses=len(g),rises=rises,falls=falls,
        pattern_pass=pattern==[1,0]*len(g),width_count=len(ws),width_error_ps=we))
codes=Counter(r['code'] for r in errors)
r=dict(pulses=len(truth),rises=sum(x['type'] for x in ts),falls=sum(not x['type'] for x in ts),
    missing_rise=missing_r,missing_fall=missing_f,extra_edges=extra,bad_sequence_groups=patterns,
    double_rise=codes[1],orphan_fall=codes[2],range_error=codes[3],conflict=codes[100],overflow=codes[101],unknown_control=codes[102],
    unexpected_output_count=len(unexpected),width_tolerance_ps=1000,max_abs_width_error_ps=maxerr,bad_width_groups=badwidth,
    FIFO_sequence_equal=[x['width_ps'] for x in fifo]==[x['width_ps'] for x in width],groups=details,
    scope='每短段4脉冲，段间200ns；按输入先后与输出R/F严格序列校验，非重新校准或逐事件精度标定')
r['functional_pass']=not any([missing_r,missing_f,extra,patterns,badwidth,len(errors),len(unexpected)]) and r['FIFO_sequence_equal']
(out/'SUMMARY.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in r.items() if k!='groups'},ensure_ascii=False,indent=2))

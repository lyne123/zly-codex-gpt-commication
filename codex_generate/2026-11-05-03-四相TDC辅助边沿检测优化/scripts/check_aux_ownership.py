"""独立核对有序辅助事件和每个确认帧的真实输入归属，不拟合补偿参数。"""
from pathlib import Path
from collections import Counter
import bisect,csv,json

ROOT=Path('W:/');MOD=2048000

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    gate=json.loads((ROOT/'results/RTL_STAGE_GATE.json').read_text(encoding='utf-8'))
    report=[];events=[];frames=[]
    for checked in gate['cases']:
        case=ROOT/'results'/checked['case'];manifest=json.loads((case/'INPUT_MANIFEST.json').read_text())
        truth=read(case/'truth.csv');epoch=int(read(case/'clock_epoch.csv')[0]['epoch_ps'])
        times={p:[int(r['rise_ps' if p else 'fall_ps']) for r in truth] for p in [0,1]}
        ids=[int(r['pulse_id']) for r in truth];aux_count=Counter();raw_count=Counter()
        auxfile=case/'aux_trace.csv'
        if not auxfile.exists():auxfile=case/'aux.csv'
        for row in read(auxfile):
            t=int(row['time_ps'])
            for p,key in [(1,'rise_slots'),(0,'fall_slots')]:
                bits=int(row[key])
                for slot in range(4):
                    if not (bits>>slot)&1:continue
                    # history及跨相位补拍后，有序事件固定在采样帧后6个0°周期形成。
                    sample=t-13000+500*(slot+1)
                    edge=sample-manifest['aux_delay_ps']
                    at=bisect.bisect_right(times[p],edge)-1
                    assert at>=0,(case,p,sample)
                    delta=edge-times[p][at]
                    assert 0<=delta<=500,(case,p,delta)
                    pid=ids[at];aux_count[pid,p]+=1
                    events.append(dict(case=case.name,pulse_id=pid,type=p,slot=slot,observed_ps=t,source_capture_clock_ps=sample,truth_input_ps=times[p][at],path_delay_ps=manifest['aux_delay_ps'],capture_interval_ps=delta))
        for row in read(case/'raw.csv'):
            t,c,mask,pol,codes=(int(row[k]) for k in ['time_ps','coarse','mask','polarity','codes'])
            owners=set()
            for index in range(4):
                if not (mask>>index)&1:continue
                typ=(pol>>(2*index))&3;assert typ in [2,3]
                p=int(typ==3);code=(codes>>(8*index))&255;tap=code if p else 64-code
                # 原locate流水线与码含义保持不变；将每相候选独立回推到输入时间。
                stamp=(((c+6)%1024)*2000+(index+1)*500-tap*10)%MOD
                wrapped=(stamp-32000-3*manifest['lut_delay_ps']+epoch)%MOD
                estimate=wrapped+round((t-20000-wrapped)/MOD)*MOD
                at=bisect.bisect_left(times[p],estimate)
                options=[j for j in [at-1,at] if 0<=j<len(ids)]
                at=min(options,key=lambda j:abs(times[p][j]-estimate))
                assert abs(times[p][at]-estimate)<=20,(case,index,estimate)
                owners.add((ids[at],p))
                frames.append(dict(case=case.name,time_ps=t,pulse_id=ids[at],type=p,index=index,code=code,input_estimate_ps=estimate,truth_ps=times[p][at]))
            assert len(owners)==1,('同一帧含不同真实事件',case,row,owners)
            raw_count[next(iter(owners))]+=1
        assert all(aux_count[i,p]==raw_count[i,p]==1 for i in ids for p in [0,1]),(case,aux_count,raw_count)
        report.append(dict(case=case.name,expected_events=2*len(ids),unique_aux_events=sum(aux_count.values()),unique_confirmation_frames=sum(raw_count.values()),pass_all=True))
    for name,rows in [('AUX_EVENT_ASSOCIATION.csv',events),('CONFIRMED_EVENT_ASSOCIATION.csv',frames)]:
        with (ROOT/'results'/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (ROOT/'results/AUX_OWNERSHIP_CHECK.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('AUX_OWNERSHIP_PASS',len(report),'cases',len(events),'unique input edges')

if __name__=='__main__':main()

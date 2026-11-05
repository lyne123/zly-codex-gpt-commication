"""只读比较同一真值/事件ID，保留失败事件；不产生或更新补偿参数。"""
from pathlib import Path
from collections import defaultdict,Counter
import csv,hashlib,json,math,statistics

ROOT=Path('W:/');OLD=Path('U:/');PREV=Path('X:/');MOD=2048000
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def stats(values):
    v=list(values)
    return dict(n=len(v),rmse_ps=math.sqrt(statistics.mean(x*x for x in v)),bias_ps=statistics.mean(v),std_ps=statistics.pstdev(v),max_abs_ps=max(map(abs,v))) if v else dict(n=0,rmse_ps=None,bias_ps=None,std_ps=None,max_abs_ps=None)
def circular(v):return (v+MOD//2)%MOD-MOD//2

def main():
    versions={'A_original_baseline':OLD/'results/original/baseline/gate_validation','B_previous_compensated':OLD/'results/optimized/compensated/gate_validation','C_aux4_compensated':ROOT/'results/compensated/gate_full','A2_optimized_baseline':OLD/'results/optimized/baseline/gate_validation','D_aux4_baseline':PREV/'results/baseline/gate_full'}
    truth=read(ROOT/'sim/stimuli/full_truth.csv');truthsha=sha(ROOT/'sim/stimuli/full_truth.csv')
    allm={};alle={};summaries={};sources={}
    for name,case in versions.items():
        assert sha(case/'truth.csv')==truthsha,name
        m=read(case/'measurements.csv');e=read(case/'associated_timestamps.csv');allm[name]={int(r['pulse_id']):r for r in m if int(r['matched'])};alle[name]={(int(r['pulse_id']),int(r['type'])):r for r in e}
        summaries[name]=json.loads((case/'summary.json').read_text());sources[name]={'path':str(case),'truth_sha256':truthsha,'measurements_sha256':sha(case/'measurements.csv'),'timestamps_sha256':sha(case/'associated_timestamps.csv')}
    common=set.intersection(*(set(allm[n]) for n in ['A_original_baseline','B_previous_compensated','C_aux4_compensated']))
    bc=set(allm['B_previous_compensated'])&set(allm['C_aux4_compensated'])
    dc=set(allm['D_aux4_baseline'])&set(allm['C_aux4_compensated'])
    report=[]
    # 各版本完整成功子集与固定相同ID集合分别列出，绝不把丢失事件隐藏在RMS中。
    for scope,ids in [('available_matched',None),('ABC_common_ids',common),('BC_common_ids',bc),('DC_common_ids',dc)]:
        for name in versions:
            chosen=set(allm[name]) if ids is None else set(allm[name])&ids
            groups=defaultdict(set)
            for pid in chosen:
                t=truth[pid];groups['all'].add(pid);groups['case:'+t['case']].add(pid);groups['nominal_period_ps:'+t['nominal_carrier_period_ps']].add(pid)
                duty=float(t['true_width_ps'])/float(t['period_ps'])*100
                groups['duty:'+('5' if abs(duty-5)<0.01 else '50' if abs(duty-50)<0.01 else '95' if abs(duty-95)<0.01 else 'other')].add(pid)
                if int(t['bank'])>=0:groups['ATC_complete_frame'].add(pid)
                if int(t['header'])>=0:groups['ATC_header_'+t['header']].add(pid)
                elif int(t['bank'])>=0:groups['SPWM_data'].add(pid)
            for group,gids in groups.items():
                for metric in ['rise','fall','pulse_width']:
                    values=[float(allm[name][i]['error_ps']) for i in gids] if metric=='pulse_width' else [float(alle[name][i,int(metric=='rise')]['error_ps']) for i in gids]
                    report.append(dict(version=name,scope=scope,group=group,metric=metric,expected_total=3512,matched_pulses=len(allm[name]),valid_rate=len(allm[name])/3512,**stats(values)))
    write(ROOT/'BASELINE_VS_COMPENSATED.csv',report)
    eventrows=[]
    for pid in range(3512):
        row=dict(pulse_id=pid,case=truth[pid]['case'],true_width_ps=truth[pid]['true_width_ps'])
        for name in versions:
            m=allm[name].get(pid);row[name+'_matched']=int(m is not None);row[name+'_width_error_ps']=m['error_ps'] if m else ''
            for pol,label in [(1,'rise'),(0,'fall')]:
                e=alle[name].get((pid,pol));row[name+'_'+label+'_error_ps']=e['error_ps'] if e else '';row[name+'_'+label+'_index']=e['index'] if e else ''
        row['C_minus_B_width_error_ps']=float(allm['C_aux4_compensated'][pid]['error_ps'])-float(allm['B_previous_compensated'][pid]['error_ps']) if pid in bc else ''
        eventrows.append(row)
    write(ROOT/'results/EVENT_COMPARISON.csv',eventrows)
    # 按实际选中的TDL/方向统计；原始时间戳由实际输出加回原参数重建并逐项校验。
    case=versions['C_aux4_compensated'];offsets={(int(r['sel_index']),int(r['polarity']=='rise')):int(r['offset_ps']) for r in read(ROOT/'inputs/frozen_compensation.csv')}
    candidates=read(case/'candidate.csv');timestamps=read(case/'timestamps.csv');edges=read(case/'associated_timestamps.csv');epoch=int(read(case/'clock_epoch.csv')[0]['epoch_ps']);audit=[];phasegroups=defaultdict(list)
    for seq,(cand,ts,e) in enumerate(zip(candidates,timestamps,edges)):
        idx=int(cand['index']);pol=int(cand['type']);code=int(cand['code']);fine=(code if pol else 64-code)*10;mid=(idx+1)*500;offset=offsets[idx,pol]
        raw=(((int(cand['coarse'])+1)%1024)*2000+mid-fine)%MOD;corrected=(raw-offset)%MOD
        assert corrected==int(ts['timestamp_ps']) and int(ts['type'])==pol and int(ts['time_ps'])-int(cand['time_ps'])==10000
        true=int(e['true_time_ps']);rawerror=circular(raw-(true-epoch)%MOD);error=circular(corrected-(true-epoch)%MOD)
        assert error==int(e['error_ps'])
        row=dict(sequence=seq,pulse_id=e['pulse_id'],tdl_phase=[90,180,270,0][idx],sel_index=idx,polarity='rise' if pol else 'fall',code=code,raw_fine_ps=fine,offset_ps=offset,raw_relative_ps=mid-fine,compensated_relative_ps=mid-fine-offset,raw_timestamp_ps=raw,actual_compensated_timestamp_ps=corrected,raw_error_ps=rawerror,compensated_error_ps=error)
        audit.append(row);phasegroups[idx,pol].append(row)
    write(ROOT/'results/SDF_COMPENSATION_TRACE.csv',audit)
    phase=[]
    for pol in [1,0]:
        raw0=statistics.mean(r['raw_error_ps'] for r in phasegroups[3,pol]);comp0=statistics.mean(r['compensated_error_ps'] for r in phasegroups[3,pol])
        for idx in [3,0,1,2]:
            g=phasegroups[idx,pol];rawmean=statistics.mean(r['raw_error_ps'] for r in g);compmean=statistics.mean(r['compensated_error_ps'] for r in g)
            phase.append(dict(tdl_phase=[90,180,270,0][idx],sel_index=idx,polarity='rise' if pol else 'fall',n=len(g),offset_ps=offsets[idx,pol],raw_fine_min_ps=min(r['raw_fine_ps'] for r in g),raw_fine_max_ps=max(r['raw_fine_ps'] for r in g),raw_bias_ps=rawmean,compensated_bias_ps=compmean,raw_relative_to_tdl0_ps=rawmean-raw0,compensated_relative_to_tdl0_ps=compmean-comp0,relative_absolute_bias_improved=abs(compmean-comp0)<=abs(rawmean-raw0),actual_output_formula_checks=len(g),sample_definition='actual selected SDF candidates; per-phase population differs; no refit'))
    write(ROOT/'PHASE_COMPENSATION_REPORT.csv',phase)
    recovery=[]
    for pid in [2917,2918,2983,2984,3049,3050]:
        rr=[e for e in edges if int(e['pulse_id'])==pid and int(e['type'])==1];ff=[e for e in edges if int(e['pulse_id'])==pid and int(e['type'])==0]
        recovery.append(dict(event_id=pid,rise_count=len(rr),fall_count=len(ff),correct_width_count=int(pid in allm['C_aux4_compensated']),pass_event=len(rr)==len(ff)==1 and pid in allm['C_aux4_compensated']))
    write(ROOT/'EVENT_RECOVERY.csv',recovery)
    # 频率切换前后事件单独保留，避免把不同频率的总表当作切换证明。
    transition=[]
    for i in range(1,len(truth)):
        a,b=truth[i-1],truth[i]
        if a['nominal_carrier_period_ps']!=b['nominal_carrier_period_ps']:
            for j in range(max(0,i-2),min(len(truth),i+3)):
                transition.append(dict(transition_at=i,from_period_ps=a['nominal_carrier_period_ps'],to_period_ps=b['nominal_carrier_period_ps'],**eventrows[j]))
    write(ROOT/'results/FREQUENCY_TRANSITIONS.csv',transition)
    result=dict(truth_sha256=truthsha,version_sources=sources,ABC_common_ids=len(common),BC_common_ids=len(bc),DC_common_ids=len(dc),parameters_recalculated=False,sdf_arithmetic_checks=len(audit),phase_bias_improved=all(r['relative_absolute_bias_improved'] for r in phase),recovered_events=all(r['pass_event'] for r in recovery),matched_counts={n:len(allm[n]) for n in versions},comparison_has_no_outlier_removal=True)
    (ROOT/'results/COMPARISON_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

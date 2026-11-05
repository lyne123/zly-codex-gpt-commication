"""按事件ID/极性及流水线发射时间匹配，保留异常，不拟合或删除样本。"""
from pathlib import Path
from collections import Counter,defaultdict
import bisect,csv,json,math,statistics
ROOT=Path('Z:/');CASE=ROOT/'results/compensated/gate_full';MOD=2048000
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows,fields=None):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def number(x):
    try:return int(x)
    except (ValueError,TypeError):return None
def stats(v):
    v=list(v)
    return dict(n=len(v),bias_ps=statistics.mean(v),rms_ps=math.sqrt(statistics.mean(x*x for x in v)),std_ps=statistics.pstdev(v),max_abs_ps=max(map(abs,v)),min_error_ps=min(v),max_error_ps=max(v)) if v else dict(n=0,bias_ps=None,rms_ps=None,std_ps=None,max_abs_ps=None,min_error_ps=None,max_error_ps=None)
def circular(x):return (x+MOD//2)%MOD-MOD//2
def main():
    assert (CASE/'run_manifest.txt').exists(),'禁止把未完成仿真的部分数据作为最终统计'
    truth=read(CASE/'truth.csv');byid={int(r['pulse_id']):r for r in truth};assert len(byid)==len(truth)==3512
    options={p:sorted((int(r['rise_ps' if p else 'fall_ps']),int(r['pulse_id'])) for r in truth) for p in [0,1]}
    times={p:[t for t,i in options[p]] for p in [0,1]}
    calibration=json.loads((ROOT/'inputs/frozen_event_association.json').read_text(encoding='utf-8'))
    offsets={(int(r['sel_index']),int(r['polarity']=='rise')):int(r['offset_ps']) for r in read(ROOT/'inputs/frozen_compensation.csv')}
    epoch=int(read(CASE/'clock_epoch.csv')[0]['epoch_ps'])
    candidates=read(CASE/'candidate.csv');ts=read(CASE/'timestamps.csv');widths=read(CASE/'widths.csv')
    candtime=defaultdict(list)
    for row in candidates:candtime[number(row['time_ps'])].append(row)
    edges=[];faults=[]
    for seq,t in enumerate(ts):
        emit=number(t['time_ps']);pol=number(t['type']);measured=number(t['timestamp_ps'])
        e=dict(row=seq,status='INVALID',event_id='',polarity=pol if pol is not None else t['type'],sel_index='',tdl_phase='',code='',candidate_time_ps='',emission_time_ps=emit,measured_timestamp_mod_ps=measured if measured is not None else t['timestamp_ps'],truth_time_ps='',unwrapped_measured_timestamp_ps='',error_ps='',association_residual_ps='',association_margin_ps='',expected_timestamp_mod_ps='',raw_fine_ps='',offset_ps='',uncorrected_error_ps='')
        cs=candtime.get(emit-10000 if emit is not None else None,[])
        if emit is None or pol not in [0,1] or measured is None or len(cs)!=1:
            faults.append(dict(kind='invalid_timestamp_or_candidate_alignment',row=seq,raw=t,candidate_matches=len(cs)));edges.append(e);continue
        c=cs[0];index=number(c['index']);code=number(c['code']);coarse=number(c['coarse'])
        if index not in range(4) or code is None or not 0<=code<=64 or coarse is None or number(c['type'])!=pol or c['conflict']!='0' or c['repeat_error']!='0':
            faults.append(dict(kind='invalid_candidate',row=seq,candidate=c));edges.append(e);continue
        target=int(c['time_ps'])-calibration['candidate_latency'][f'{index},{pol}']
        at=bisect.bisect_left(times[pol],target);near=[k for k in [at-1,at] if 0<=k<len(times[pol])]
        distances=sorted((abs(times[pol][k]-target),k) for k in near);residual,k=distances[0];margin=distances[1][0]-residual if len(distances)>1 else MOD
        actual,pid=options[pol][k];fine=(code if pol else 64-code)*10;offset=offsets[index,pol]
        uncorrected=(((coarse+1)%1024)*2000+(index+1)*500-fine)%MOD;expected=(uncorrected-offset)%MOD
        # 仅按已冻结发射延迟确定事件ID/回卷周次，不从验证集拟合公共偏移或补偿值。
        unwrapped=measured+epoch+round((target-measured-epoch)/MOD)*MOD
        e.update(status='MATCHED',event_id=pid,sel_index=index,tdl_phase=[90,180,270,0][index],code=code,candidate_time_ps=int(c['time_ps']),truth_time_ps=actual,unwrapped_measured_timestamp_ps=unwrapped,error_ps=unwrapped-actual,association_residual_ps=residual,association_margin_ps=margin,expected_timestamp_mod_ps=expected,raw_fine_ps=fine,offset_ps=offset,uncorrected_error_ps=circular(uncorrected-(actual-epoch)%MOD))
        if residual>2000 or margin<=0:
            e['status']='UNMATCHED';faults.append(dict(kind='unmatched_or_ambiguous_event',row=seq,event_id=pid,residual_ps=residual,margin_ps=margin))
        if measured!=expected:
            e['status']='ARITHMETIC_ERROR';faults.append(dict(kind='timestamp_formula',row=seq,measured=measured,expected=expected))
        edges.append(e)
    write(ROOT/'results/EDGE_RESULTS.csv',edges)
    good=[e for e in edges if e['status']=='MATCHED'];edgecounts={p:Counter(int(e['event_id']) for e in good if e['polarity']==p) for p in [0,1]}
    pending=None;pairs_by_width_time={};pairfaults=[]
    for e in edges:
        if e['status']!='MATCHED':continue
        if e['polarity']==1:
            if pending:pairfaults.append(dict(kind='consecutive_rises',previous_id=pending['event_id'],next_id=e['event_id']))
            pending=e
        elif pending:
            pairs_by_width_time[e['emission_time_ps']+6000]=(pending,e);pending=None
        else:pairfaults.append(dict(kind='orphan_fall',event_id=e['event_id']))
    if pending:pairfaults.append(dict(kind='unclosed_rise',event_id=pending['event_id']))
    pulses=[]
    for seq,w in enumerate(widths):
        emit=number(w['time_ps']);value=number(w['width_ps']);pair=pairs_by_width_time.get(emit)
        m=dict(row=seq,status='UNMATCHED',event_id='',rise_event_id='',fall_event_id='',emission_time_ps=emit,measured_width_ps=value if value is not None else w['width_ps'],truth_width_ps='',error_ps='',rise_timestamp_mod_ps='',fall_timestamp_mod_ps='',case='',nominal_carrier_period_ps='',duty_percent='',bank='',channel='',header='')
        if pair and value is not None:
            r,f=pair;pid=int(f['event_id']);t=byid[pid]
            m.update(status='MATCHED' if r['event_id']==f['event_id'] else 'MISPAIR',event_id=pid,rise_event_id=r['event_id'],fall_event_id=f['event_id'],truth_width_ps=int(t['true_width_ps']),error_ps=value-int(t['true_width_ps']),rise_timestamp_mod_ps=r['measured_timestamp_mod_ps'],fall_timestamp_mod_ps=f['measured_timestamp_mod_ps'],case=t['case'],nominal_carrier_period_ps=t['nominal_carrier_period_ps'],duty_percent=100*int(t['true_width_ps'])/int(t['period_ps']),bank=t['bank'],channel=t['channel'],header=t['header'])
            expected=(f['measured_timestamp_mod_ps']-r['measured_timestamp_mod_ps'])%MOD
            if value!=expected:m['status']='ARITHMETIC_ERROR';faults.append(dict(kind='width_formula',row=seq,value=value,expected=expected))
        if m['status']!='MATCHED':faults.append(dict(kind='width_'+m['status'],row=seq,details=m))
        pulses.append(m)
    write(ROOT/'results/PULSE_RESULTS.csv',pulses)
    correct=[p for p in pulses if p['status']=='MATCHED'];pc=Counter(int(p['event_id']) for p in correct)
    missing={p:sorted(set(byid)-set(edgecounts[p])) for p in [0,1]};duplicate={p:sorted(i for i,n in edgecounts[p].items() if n>1) for p in [0,1]}
    raw_invalid=[]
    for seq,row in enumerate(read(CASE/'raw.csv')):
        values={k:number(row[k]) for k in ['mask','polarity','codes']}
        if any(v is None for v in values.values()):raw_invalid.append(dict(row=seq,raw=row));continue
        for index in range(4):
            if values['mask']&(1<<index):
                code=(values['codes']>>(index*8))&255;polarity=(values['polarity']>>(index*2))&3
                if code>64 or polarity not in [2,3]:raw_invalid.append(dict(row=seq,index=index,code=code,polarity=polarity))
    fifo=read(CASE/'fifo.csv');errors=read(CASE/'errors.csv');error_fifo=read(CASE/'error_fifo.csv')
    writes=read(CASE/'FIFO_WRITES.csv');reads=read(CASE/'FIFO_READS.csv');wr=[r for r in writes if r['kind']=='result'];rd=[r for r in reads if r['kind']=='result']
    fifo_sequence=[r['width_ps'] for r in fifo]==[r['width_ps'] for r in widths]
    write_sequence=[r['data'] for r in wr]==[r['width_ps'] for r in widths]
    fifo_pass=fifo_sequence and write_sequence and len(wr)==len(rd)==len(fifo)==len(widths)==3512 and not error_fifo and not any(r['kind']=='error' for r in writes+reads) and not any(r['full']!='0' or r['busy']!='0' for r in wr) and not any(r['empty']!='0' or r['busy']!='0' for r in rd) and not any(r['kind']=='overflow' for r in errors)
    reset=read(CASE/'RESET_TRACE.csv');releases={s:[r for r in reset if r['signal']==s and r['value']=='1'] for s in ['original','replica']}
    reset_pass=all(len(x)==1 for x in releases.values())
    if reset_pass:
        a,b=releases['original'][0],releases['replica'][0]
        reset_pass=a['own_clock_cycles']==b['own_clock_cycles'] and a['MMCM_locked']==b['MMCM_locked']=='1' and max(int(a['time_ps']),int(b['time_ps']))<min(int(r['rise_ps']) for r in truth)
    aux=read(CASE/'aux_events.csv');auxcount={p:sum(number(r[key]).bit_count() for r in aux if number(r[key]) is not None) for p,key in [(1,'rise_slots'),(0,'fall_slots')]};aux_unknown=sum(number(r[key]) is None for r in aux for key in ['rise_slots','fall_slots'])
    functional=len(ts)==len(candidates)==7024 and len(correct)==len(pc)==3512 and not faults and not pairfaults and not any(missing.values()) and not any(duplicate.values()) and not raw_invalid and not errors and not error_fifo and auxcount[1]==auxcount[0]==3512 and not aux_unknown
    groups=defaultdict(list)
    for p in correct:
        keys=['all','case:'+p['case'],'nominal_period_ps:'+p['nominal_carrier_period_ps']]
        duty=p['duty_percent'];keys+=['duty:'+('5' if abs(duty-5)<0.01 else '50' if abs(duty-50)<0.01 else '95' if abs(duty-95)<0.01 else 'other')]
        if int(p['bank'])>=0:keys+=['ATC_all','ATC_header_'+p['header'] if int(p['header'])>=0 else 'SPWM_data']
        for key in keys:groups[key].append(p['error_ps'])
    phasereport=[]
    for polarity in [1,0]:
        zero=[e for e in good if e['polarity']==polarity and e['sel_index']==3];base0=statistics.mean(e['uncorrected_error_ps'] for e in zero) if zero else None;comp0=statistics.mean(e['error_ps'] for e in zero) if zero else None
        for index in [3,0,1,2]:
            es=[e for e in good if e['polarity']==polarity and e['sel_index']==index];before=stats(e['uncorrected_error_ps'] for e in es);after=stats(e['error_ps'] for e in es)
            phasereport.append(dict(tdl_phase=[90,180,270,0][index],sel_index=index,polarity='rise' if polarity else 'fall',n=len(es),offset_ps=offsets[index,polarity],raw_bias_ps=before['bias_ps'],compensated_bias_ps=after['bias_ps'],raw_relative_to_TDL0_ps=before['bias_ps']-base0 if es and base0 is not None else '',compensated_relative_to_TDL0_ps=after['bias_ps']-comp0 if es and comp0 is not None else '',compensated_rms_ps=after['rms_ps'],compensated_std_ps=after['std_ps'],compensated_max_abs_ps=after['max_abs_ps'],population='actual selected candidates; different phase sampling populations; no refit'))
    write(ROOT/'results/PHASE_COMPENSATION_REPORT.csv',phasereport)
    recovery=[dict(event_id=i,rise_count=edgecounts[1][i],fall_count=edgecounts[0][i],correct_width_count=pc[i],pass_event=edgecounts[1][i]==edgecounts[0][i]==pc[i]==1) for i in [2917,2918,2983,2984,3049,3050]]
    write(ROOT/'results/EVENT_RECOVERY.csv',recovery)
    result=dict(expected_pulses=3512,expected_edges=7024,actual_edges=len(ts),actual_widths=len(widths),correct_pulses=len(pc),valid_rate=len(pc)/3512,missing_rise_ids=missing[1],missing_fall_ids=missing[0],duplicate_rise_ids=duplicate[1],duplicate_fall_ids=duplicate[0],missing_pulse_ids=sorted(set(byid)-set(pc)),duplicate_pulse_ids=sorted(i for i,n in pc.items() if n>1),mispairs=sum(p['status']=='MISPAIR' for p in pulses),unmatched_or_invalid_edges=sum(e['status']!='MATCHED' for e in edges),invalid_raw_edges=len(raw_invalid),business_errors=errors,error_fifo=error_fifo,arithmetic_or_association_faults=faults,pairing_faults=pairfaults,functional_pass=functional,fifo_pass=fifo_pass,fifo_writes=len(wr),fifo_reads=len(rd),fifo_outputs=len(fifo),fifo_sequence_equal=fifo_sequence,fifo_write_sequence_equal=write_sequence,reset_pass=reset_pass,reset_releases=releases,first_pulse=next((p for p in correct if int(p['event_id'])==min(byid)),None),aux_rises=auxcount[1],aux_falls=auxcount[0],epoch_ps=epoch,minimum_association_margin_ps=min((e['association_margin_ps'] for e in good),default=None),maximum_association_residual_ps=max((e['association_residual_ps'] for e in good),default=None),rise=stats(e['error_ps'] for e in good if e['polarity']==1),fall=stats(e['error_ps'] for e in good if e['polarity']==0),pulse_width=stats(p['error_ps'] for p in correct),groups={k:stats(v) for k,v in groups.items()},precision_complete=functional and len(good)==7024,parameters_recalibrated=False,outlier_removal=False,timestamp_error_definition='unwrapped(measured_mod + observed_epoch, cycle chosen from frozen event-association latency) - absolute truth; no bias subtraction',STD_definition='population STD: sqrt(mean((error-bias)^2))',RMS_definition='sqrt(mean(error^2))')
    (ROOT/'results/ERROR_STATISTICS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'results/INVALID_RAW_EDGES.json').write_text(json.dumps(raw_invalid,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['functional_pass','correct_pulses','actual_edges','mispairs','fifo_pass','reset_pass','rise','fall','pulse_width']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()

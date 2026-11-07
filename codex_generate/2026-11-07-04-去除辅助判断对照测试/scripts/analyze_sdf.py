"""按冻结发射延迟、原始事件ID和实际FIFO序列分析，不拟合偏移、不删除异常。"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,bisect,csv,gzip,json,math,re,statistics
TASK=Path(__file__).resolve().parents[1];MOD=2048000
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def num(x):
    try:return int(x)
    except (ValueError,TypeError):return None
def stats(values):
    values=list(values);n=len(values)
    return dict(n=n,bias_ps=statistics.mean(values),rmse_ps=math.sqrt(statistics.mean(x*x for x in values)),
        std_sample_ps=statistics.stdev(values) if n>1 else None,std_population_ps=statistics.pstdev(values),max_abs_ps=max(map(abs,values))) if n else dict(n=0)
def write(p,rows,fields):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=['noaux'],default='noaux');ap.add_argument('--dataset',choices=['minimal','full'],default='minimal');a=ap.parse_args()
    case=TASK/'results/sdf'/a.variant/a.dataset
    assert json.loads((case/'RUN_MANIFEST.json').read_text(encoding='utf-8'))['completed']
    extra=json.loads((case.parent/'ANNOTATION.json').read_text(encoding='utf-8'))['input_extra_cycles']
    truth=read(case/'truth.csv');byid={int(r['pulse_id']):r for r in truth};n=len(truth)
    options={p:sorted((int(r['rise_ps' if p else 'fall_ps']),int(r['pulse_id'])) for r in truth) for p in [0,1]}
    times={p:[x[0] for x in options[p]] for p in [0,1]}
    calibration=json.loads((TASK/'inputs/frozen_event_association.json').read_text(encoding='utf-8'))
    offsets={(int(r['sel_index']),int(r['polarity']=='rise')):int(r['offset_ps']) for r in read(TASK/'inputs/frozen_compensation.csv')}
    epoch=int(read(case/'epoch.csv')[0]['epoch_ps']);cand=read(case/'candidate.csv');ts=read(case/'timestamps.csv');width=read(case/'widths.csv');errors=read(case/'errors.csv');fifo=read(case/'fifo.csv');errfifo=read(case/'error_fifo.csv')
    ct=defaultdict(list)
    for c in cand:ct[num(c['time_ps'])].append(c)
    edge=[];faults=[]
    for k,t in enumerate(ts):
        emit,pol,value=map(num,[t['time_ps'],t['type'],t['timestamp_ps']]);cs=ct.get(emit-10000 if emit is not None else None,[])
        r=dict(row=k,status='INVALID',event_id='',polarity=pol,emission_ps=emit,timestamp_ps=value,index='',code='',truth_ps='',error_ps='',residual_ps='')
        if pol in [0,1] and value is not None and len(cs)==1:
            c=cs[0];idx,code,coarse=map(num,[c['index'],c['code'],c['coarse']])
            if idx in range(4) and code is not None and 0<=code<=64 and coarse is not None:
                target=emit-10000-calibration['candidate_latency'][f'{idx},{pol}']-extra*2000
                j=bisect.bisect_left(times[pol],target);near=[i for i in [j-1,j] if 0<=i<len(times[pol])]
                distances=sorted((abs(times[pol][i]-target),i) for i in near);residual,i=distances[0];time,pid=options[pol][i]
                margin=distances[1][0]-residual if len(distances)>1 else MOD
                fine=(code if pol else 64-code)*10
                expected=((((coarse+1)%1024)*2000+(idx+1)*500-fine)-offsets[idx,pol])%MOD
                status='MATCHED' if residual<=2000 and margin>0 else 'UNMATCHED'
                if value!=expected:status='ARITHMETIC_ERROR'
                if num(c['type'])!=pol or c['conflict']!='0':status='INVALID_CANDIDATE'
                unwrapped=value+epoch+round((target-value-epoch)/MOD)*MOD
                r.update(status=status,event_id=pid,index=idx,code=code,truth_ps=time,error_ps=unwrapped-time,residual_ps=residual)
        if r['status']!='MATCHED':faults.append(dict(kind='edge_'+r['status'],row=k))
        edge.append(r)
    good=[r for r in edge if r['status']=='MATCHED'];counts={p:Counter(r['event_id'] for r in good if r['polarity']==p) for p in [0,1]}
    pending=None;pairs={};pairfaults=[]
    for r in edge:
        if r['status']!='MATCHED':continue
        if r['polarity']:
            if pending:pairfaults.append(dict(kind='repeat_rise',previous=pending['event_id'],next=r['event_id']))
            pending=r
        elif pending:pairs[r['emission_ps']+6000]=(pending,r);pending=None
        else:pairfaults.append(dict(kind='orphan_fall',event_id=r['event_id']))
    if pending:pairfaults.append(dict(kind='unclosed_rise',event_id=pending['event_id']))
    pulses=[]
    for k,w in enumerate(width):
        emit,value=map(num,[w['time_ps'],w['width_ps']]);pair=pairs.get(emit)
        r=dict(row=k,status='UNMATCHED',event_id='',rise_id='',fall_id='',width_ps=value,truth_width_ps='',error_ps='',case='')
        if pair and value is not None:
            up,down=pair;pid=down['event_id'];t=byid[pid]
            status='MATCHED' if up['event_id']==pid else 'MISPAIR'
            if value!=(down['timestamp_ps']-up['timestamp_ps'])%MOD:status='ARITHMETIC_ERROR'
            r.update(status=status,event_id=pid,rise_id=up['event_id'],fall_id=pid,truth_width_ps=int(t['true_width_ps']),error_ps=value-int(t['true_width_ps']),case=t['case'])
        if r['status']!='MATCHED':faults.append(dict(kind='pulse_'+r['status'],row=k))
        pulses.append(r)
    correct=[r for r in pulses if r['status']=='MATCHED'];pc=Counter(r['event_id'] for r in correct)
    warn=Counter();first={};last={}
    with gzip.open(case/'simulation.log.gz','rt',encoding='utf-8',errors='replace') as f:
        for line in f:
            if 'WARNING:' not in line and 'ERROR:' not in line:continue
            if 'Timing violation in scope' not in line:key='other_warning_or_error'
            elif 'mmcm_adv_inst' in line and re.search(r'\$period.*CLKOUT[56]',line):key='unused_MMCM_CLKOUT5_6_zero_period'
            # 仅分类复位同步器第一级、epoch前的异步释放告警；下游或运行期间告警仍阻断。
            elif re.search(r'/rst_sync_(?:0|90|180|270)_reg\[0\]/',line) and '$recrem' in line and (when_match:=re.search(r'at time (\d+) ps',line)) and int(when_match[1])<epoch:key='startup_async_reset_first_stage'
            elif 'pwm_meta_reg' in line:key='asynchronous_aux_first_sampler'
            elif re.search(r'/u_tdl(?:0|90|180|270)/',line) and 'thermo_q_reg' in line:key='asynchronous_TDL_thermometer_sampler'
            elif '/u_ila2/' in line or '/u_ila3/' in line:key='non_feedback_ILA'
            else:key='core_synchronous_or_unclassified'
            warn[key]+=1
            t=re.search(r'at time (\d+) ps',line)
            if t:
                when=int(t[1]);first.setdefault(key,when);last[key]=when
    warning_gate=warn['core_synchronous_or_unclassified']==0 and warn['other_warning_or_error']==0
    missing={p:sorted(set(byid)-set(counts[p])) for p in [0,1]}
    duplicates={p:sorted(i for i,v in counts[p].items() if v>1) for p in [0,1]}
    fifo_equal=[r['width_ps'] for r in fifo]==[r['width_ps'] for r in width]
    functional=(len(ts)==len(cand)==2*n and len(correct)==len(pc)==n and not faults and not pairfaults and
        not any(missing.values()) and not any(duplicates.values()) and not errors and not errfifo and fifo_equal and len(fifo)==n)
    maxerror=max((abs(r['error_ps']) for r in correct),default=None)
    widthpass=maxerror is not None and maxerror<=1000
    result=dict(variant=a.variant,dataset=a.dataset,expected_pulses=n,actual_edges=len(ts),actual_widths=len(width),correct_pairs=len(pc),
        missing_rise_ids=missing[1],missing_fall_ids=missing[0],duplicate_rise_ids=duplicates[1],duplicate_fall_ids=duplicates[0],
        mispairs=sum(r['status']=='MISPAIR' for r in pulses),faults=faults,pairing_faults=pairfaults,business_errors=errors,error_fifo=errfifo,
        FIFO_sequence_equal=fifo_equal,FIFO_outputs=len(fifo),functional_pass=functional and widthpass,
        timing_warning_gate_pass=warning_gate,MAX_SDF_pass=functional and widthpass and warning_gate,
        warning_counts=dict(warn),warning_first_ps=first,warning_last_ps=last,width_tolerance_ps=1000,input_extra_cycles=extra,
        pulse_width=stats(r['error_ps'] for r in correct),rise=stats(r['error_ps'] for r in good if r['polarity']==1),fall=stats(r['error_ps'] for r in good if r['polarity']==0),
        groups={name:stats(r['error_ps'] for r in correct if r['case']==name) for name in dict.fromkeys(r['case'] for r in truth)},
        parameters_refitted=False,outliers_removed=False,epoch_ps=epoch,formula='Bias=mean(error); RMSE=sqrt(mean(error^2)); STD=sqrt(sum((error-Bias)^2)/(N-1)); no sqrt(2) divisor')
    write(case/'EDGE_RESULTS.csv',edge,list(edge[0]) if edge else ['status'])
    write(case/'PULSE_RESULTS.csv',pulses,list(pulses[0]) if pulses else ['status'])
    (case/'SUMMARY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['variant','dataset','correct_pairs','actual_edges','functional_pass','MAX_SDF_pass','warning_counts','pulse_width']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()

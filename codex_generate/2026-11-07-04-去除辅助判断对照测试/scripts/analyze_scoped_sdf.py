"""只按用户确认的输入高低间隔划分范围，保留原完整SDF结论与全部事件。"""
from pathlib import Path
from collections import Counter
import argparse,bisect,json
from analyze_sdf import read,stats,write
TASK=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dataset',choices=['minimal','full'],required=True);a=parser.parse_args()
    case=TASK/'results/sdf/noaux'/a.dataset
    original=json.loads((case/'SUMMARY.json').read_text(encoding='utf-8'))
    truth=read(case/'truth.csv');all_ids={int(r['pulse_id']) for r in truth};excluded=set();gaps=[]
    for r in truth:
        if int(r['fall_ps'])-int(r['rise_ps'])<2000:excluded.add(int(r['pulse_id']))
    for left,right in zip(truth,truth[1:]):
        gap=int(right['rise_ps'])-int(left['fall_ps'])
        if gap<2000:
            i,j=int(left['pulse_id']),int(right['pulse_id']);excluded.update([i,j]);gaps.append(dict(left=i,right=j,low_gap_ps=gap))
    scope=all_ids-excluded
    if a.dataset=='full':
        accepted=json.loads((TASK/'results/SCOPED_RTL_GATE.json').read_text(encoding='utf-8'))
        assert accepted['user_scope_confirmed'] and scope==set(accepted['scope_ids'])
    else:assert not excluded,'最小输入的范围发生变化，须审计而非排除失败点'
    pulses=read(case/'PULSE_RESULTS.csv');edges=read(case/'EDGE_RESULTS.csv')
    matched=[r for r in pulses if r['status']=='MATCHED' and int(r['event_id']) in scope]
    good_ids=Counter(int(r['event_id']) for r in matched)
    violations=[]
    for r in pulses:
        if r['status']!='MATCHED':
            # 只有明确归属于范围外输入的错配才可单独报告；未知和计算错误始终阻断。
            if not(r['status']=='MISPAIR' and r['rise_id']!='' and r['fall_id']!='' and int(r['rise_id']) in excluded and int(r['fall_id']) in excluded):
                violations.append(dict(kind='pulse_'+r['status'],row=r['row']))
    for r in edges:
        if r['status']!='MATCHED':violations.append(dict(kind='edge_'+r['status'],row=r['row']))
    counts={p:Counter(int(r['event_id']) for r in edges if r['status']=='MATCHED' and int(r['polarity'])==p and int(r['event_id']) in scope) for p in [0,1]}
    for p in [0,1]:
        for pid in sorted(scope):
            if counts[p][pid]!=1:violations.append(dict(kind='edge_count',polarity=p,event_id=pid,count=counts[p][pid]))
    for pid in sorted(scope):
        if good_ids[pid]!=1:violations.append(dict(kind='pulse_count',event_id=pid,count=good_ids[pid]))
    for f in original['pairing_faults']:
        ids=[int(f[k]) for k in ['event_id','previous','next'] if k in f]
        if not ids or any(i in scope for i in ids):violations.append(dict(kind='pairing_fault',detail=f))
    # 混合极性冲突按原始候选帧与冻结发射延迟关联；无法归属的错误绝不静默忽略。
    raw={int(r['time_ps']):r for r in read(case/'raw.csv')}
    calibration=json.loads((TASK/'inputs/frozen_event_association.json').read_text(encoding='utf-8'))
    options={p:sorted((int(r['rise_ps' if p else 'fall_ps']),int(r['pulse_id'])) for r in truth) for p in [0,1]}
    times={p:[t for t,i in options[p]] for p in [0,1]}
    # 按未修改的Merge Stage1逐事件重放错误条件；固定一拍=2000ps，不拟合延迟。
    # 先要求实际错误时间/错误码与重放严格一致，才允许依据输入ID划分范围。
    edge_at={int(r['emission_ps']):r for r in edges if r['status']=='MATCHED'}
    previous_edge={};last=None;pending=None;merge_expected={}
    replay_known=all(r['status']=='MATCHED' for r in edges)
    if replay_known:
        for r in edges:
            emit=int(r['emission_ps']);pid=int(r['event_id']);pol=int(r['polarity'])
            previous_edge[emit]=last
            if int(r['timestamp_ps'])>=2048000:
                merge_expected[emit+2000]=(3,[pid]);pending=None
            elif pol:
                if pending is not None:merge_expected[emit+2000]=(1,[int(pending['event_id']),pid])
                pending=r
            elif pending is not None:pending=None
            else:merge_expected[emit+2000]=(2,[pid])
            last=r
        actual_merge={(int(e['time_ps']),int(e['code'])) for e in original['business_errors'] if int(e['code']) in [1,2,3]}
        replay_merge={(t,code) for t,(code,ids) in merge_expected.items()}
        replay_known=actual_merge==replay_merge
        if not replay_known:violations.append(dict(kind='merge_error_replay_mismatch',actual=sorted(actual_merge),expected=sorted(replay_merge)))
    errors_classified=[]
    for error in original['business_errors']:
        ids=[];known=True
        if int(error['code'])==100:
            frame=raw.get(int(error['time_ps'])-10000)
            if frame:
                mask,pol=int(frame['mask']),int(frame['polarity'])
                for phase in range(4):
                    if not(mask>>phase&1):continue
                    typ=pol>>(phase*2)&3
                    if typ not in [2,3]:known=False;continue
                    p=int(typ==3)
                    target=int(error['time_ps'])-calibration['candidate_latency'][f'{phase},{p}']-original['input_extra_cycles']*2000
                    j=bisect.bisect_left(times[p],target);near=[i for i in [j-1,j] if 0<=i<len(times[p])]
                    distance,i=min((abs(times[p][i]-target),i) for i in near)
                    if distance>2000:known=False
                    ids.append(options[p][i][1])
            else:known=False
        elif int(error['code'])==103 and replay_known:
            # testbench的103来自候选输出的连续同极性；Locate恰为5拍=10000ps。
            edge=edge_at.get(int(error['time_ps'])+10000)
            prev=previous_edge.get(int(error['time_ps'])+10000)
            if edge and prev and edge['polarity']==prev['polarity']:
                ids=[int(prev['event_id']),int(edge['event_id'])]
            else:known=False
        elif int(error['code']) in [1,2,3] and replay_known:
            expected=merge_expected.get(int(error['time_ps']))
            if expected and expected[0]==int(error['code']):ids=expected[1]
            else:known=False
        else:known=False
        outside=known and bool(ids) and all(i in excluded for i in ids)
        errors_classified.append(dict(**error,event_ids=ids,classification='OUT_OF_SCOPE' if outside else 'BLOCKING',
                                      basis='固定RTL流水和实际事件ID；Merge错误另经状态重放校验'))
        if not outside:violations.append(dict(kind='unclassified_or_in_scope_error',detail=error))
    invalid_raw=[]
    for r in raw.values():
        mask,pol,codes=int(r['mask']),int(r['polarity']),int(r['codes'])
        for phase in range(4):
            if mask>>phase&1:
                typ,code=pol>>(phase*2)&3,codes>>(phase*8)&255
                if not ((typ==3 and 1<=code<=60) or (typ==2 and 5<=code<=63)):
                    invalid_raw.append(dict(time_ps=int(r['time_ps']),phase=phase,type=typ,code=code))
    if invalid_raw:violations.append(dict(kind='accepted_out_of_range',rows=invalid_raw))
    if not original['FIFO_sequence_equal']:violations.append(dict(kind='FIFO_sequence'))
    error_fifo=read(case/'error_fifo.csv')
    merge_errors=[r for r in read(case/'errors.csv') if int(r['code']) in [1,2,3]]
    if [r['code'] for r in error_fifo]!=[r['code'] for r in merge_errors]:violations.append(dict(kind='error_FIFO_sequence'))
    values=[int(r['error_ps']) for r in matched]
    accuracy=bool(values) and max(map(abs,values))<=original['width_tolerance_ps']
    result=dict(dataset=a.dataset,scope='input high>=2000ps AND adjacent low>=2000ps',
        full_input_pulses=len(truth),scope_pulses=len(scope),scope_correct_pulses=len(good_ids),
        excluded_ids=sorted(excluded),short_gaps=gaps,original_full_functional_pass=original['functional_pass'],
        original_full_MAX_SDF_pass=original['MAX_SDF_pass'],scope_violations=violations,
        original_errors_classified=errors_classified,accepted_out_of_range=invalid_raw,
        merge_error_replay_exact=replay_known,merge_error_output_cycles=1,candidate_to_timestamp_cycles=5,
        scope_pulse_width=stats(values),scope_groups={name:stats(int(r['error_ps']) for r in matched if r['case']==name) for name in dict.fromkeys(r['case'] for r in truth)},
        timing_warning_gate_pass=original['timing_warning_gate_pass'],
        pass_all=not violations and len(matched)==len(scope) and accuracy and original['timing_warning_gate_pass'],
        input_waveform_changed=False,thresholds_changed=False,parameters_refitted=False,
        scope_selection_uses_only_true_input_times=True,original_failure_summary_preserved=True)
    (case/'SCOPED_SUMMARY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    write(case/'SCOPED_PULSE_RESULTS.csv',matched,list(pulses[0]))
    print(json.dumps({k:result[k] for k in ['dataset','scope_pulses','scope_correct_pulses','pass_all','original_full_MAX_SDF_pass','scope_violations','scope_pulse_width']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()

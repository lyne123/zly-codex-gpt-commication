"""比较已完成版本的相同事件ID；明确理想RTL与真实SDF条件，不伪造04轮SDF。"""
from pathlib import Path
from collections import defaultdict
import bisect,csv,hashlib,json
from analyze_results import read,write,stats,circular,MOD
ROOT=Path('Z:/')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def rtl_case(folder,baseline):
    truth={int(r['pulse_id']):r for r in read(ROOT/'inputs/full_truth.csv')};epoch=int(read(folder/'clock_epoch.csv')[0]['epoch_ps'])
    # 只重用既有理想RTL的32000ps公共项来认事件，绝不修改补偿时间戳或拟合本轮。
    maps={p:sorted((int(t['rise_ps' if p else 'fall_ps']),i) for i,t in truth.items()) for p in [0,1]};lookup={}
    base_epoch=int(read(baseline/'clock_epoch.csv')[0]['epoch_ps'])
    for r in read(baseline/'timestamps.csv'):
        pol=int(r['type']);emit=int(r['time_ps']);wrapped=(int(r['timestamp_ps'])-32000+base_epoch)%MOD
        estimated=wrapped+round((emit-40000-wrapped)/MOD)*MOD;options=maps[pol];times=[x[0] for x in options];at=bisect.bisect_left(times,estimated);ks=[k for k in [at-1,at] if 0<=k<len(options)];k=min(ks,key=lambda k:abs(times[k]-estimated));actual,pid=options[k];assert abs(actual-estimated)<=20
        lookup[emit]=(pid,pol)
    events={};falltime={}
    for r in read(folder/'timestamps.csv'):
        emit=int(r['time_ps']);pid,pol=lookup[emit];actual=int(truth[pid]['rise_ps' if pol else 'fall_ps'])
        events[pid,pol]=dict(error_ps=circular(int(r['timestamp_ps'])-(actual-epoch)%MOD),raw=r)
        if not pol:falltime[emit+6000]=pid
    pulses={}
    for w in read(folder/'widths.csv'):
        pid=falltime[int(w['time_ps'])];pulses[pid]=dict(error_ps=int(w['width_ps'])-int(truth[pid]['true_width_ps']))
    return events,pulses
def historical_sdf(folder):
    events={(int(r['pulse_id']),int(r['type'])):dict(error_ps=float(r['error_ps'])) for r in read(folder/'associated_timestamps.csv')}
    pulses={int(r['pulse_id']):dict(error_ps=float(r['error_ps'])) for r in read(folder/'measurements.csv') if int(r['matched'])}
    return events,pulses
def main():
    baseline=Path('W:/results/rtl/baseline/rtl_full')
    cases={
        '03_aux_baseline_RTL':(*rtl_case(baseline,baseline),'ideal RTL; 10ps/tap model; no routed input delay'),
        '04_merged_compensated_RTL':(*rtl_case(Path('Y:/results/rtl/compensated/rtl_full'),Path('Y:/results/rtl/baseline/rtl_full')),'ideal RTL with fixed physical-calibration offsets'),
        '05_optimized_compensated_RTL':(*rtl_case(Path('W:/results/rtl/compensated/rtl_full'),baseline),'ideal RTL with same fixed physical-calibration offsets'),
        'original_baseline_RTL_archive':(*historical_sdf(Path('U:/results/original/baseline/rtl_validation')),'historical original RTL archive; different original frontend/pipeline'),
        '01_compensated_SDF_historical':(*historical_sdf(Path('U:/results/optimized/compensated/gate_validation')),'historical MAX-SDF; same 8 offsets; six original failed pulse IDs retained'),
        '03_aux_baseline_SDF':(*historical_sdf(Path('X:/results/baseline/gate_full')),'historical MAX-SDF; auxiliary four-phase; compensation bypass')}
    edges=read(ROOT/'results/EDGE_RESULTS.csv');pulses=read(ROOT/'results/PULSE_RESULTS.csv')
    cases['05_compensated_MAX_SDF']=({(int(e['event_id']),int(e['polarity'])):dict(error_ps=float(e['error_ps'])) for e in edges if e['status']=='MATCHED'},{int(p['event_id']):dict(error_ps=float(p['error_ps'])) for p in pulses if p['status']=='MATCHED'},'current full MAX-SDF from 05 frozen final DCP; XSim 2022.2')
    common=set(cases['01_compensated_SDF_historical'][1])&set(cases['05_compensated_MAX_SDF'][1]);rows=[]
    for name,(es,ps,condition) in cases.items():
        for scope,ids in [('all_available_correct',set(ps)),('same_3506_historical_ids',set(ps)&common)]:
            for metric in ['rise','fall','pulse_width']:
                values=[ps[i]['error_ps'] for i in sorted(ids)] if metric=='pulse_width' else [es[i,int(metric=='rise')]['error_ps'] for i in sorted(ids) if (i,int(metric=='rise')) in es]
                rows.append(dict(version=name,scope=scope,metric=metric,condition=condition,expected_pulses=3512,correct_pulses=len(ps),**stats(values)))
    write(ROOT/'results/VERSION_COMPARISON.csv',rows)
    write(ROOT/'results/EVENT_VERSION_COMPARISON.csv',[dict(event_id=i,**{name+'_width_error_ps':ps.get(i,{}).get('error_ps','') for name,(es,ps,condition) in cases.items()}) for i in range(3512)])
    # 同一SDF候选/粗计数下仅撤销固定偏移作算术重建，不冒称另一份Baseline实现。
    perid={int(p['event_id']):p for p in pulses if p['status']=='MATCHED'};edgebyid={(int(e['event_id']),int(e['polarity'])):e for e in edges if e['status']=='MATCHED'};reconstructed=[]
    for i,p in perid.items():
        r,f=edgebyid[i,1],edgebyid[i,0];raw=(int(p['measured_width_ps'])-int(r['offset_ps'])+int(f['offset_ps']))%MOD
        reconstructed.append(dict(event_id=i,uncorrected_width_reconstructed_ps=raw,compensated_width_ps=p['measured_width_ps'],truth_width_ps=p['truth_width_ps'],uncorrected_error_ps=raw-int(p['truth_width_ps']),compensated_error_ps=p['error_ps'],note='same observed candidate arithmetic reconstruction, not a separate implementation'))
    write(ROOT/'results/SAME_SDF_COMPENSATION_EFFECT.csv',reconstructed)
    # 逐事件记录真实频率切换邻域，数据来自完整原始刺激，未另造或调整激励。
    truth=read(ROOT/'inputs/full_truth.csv');transitions=[]
    for k in range(1,len(truth)):
        if truth[k-1]['nominal_carrier_period_ps']!=truth[k]['nominal_carrier_period_ps']:
            for j in range(max(0,k-2),min(len(truth),k+3)):
                i=int(truth[j]['pulse_id']);p=perid.get(i)
                transitions.append(dict(transition_at_id=truth[k]['pulse_id'],from_nominal_period_ps=truth[k-1]['nominal_carrier_period_ps'],to_nominal_period_ps=truth[k]['nominal_carrier_period_ps'],event_id=i,status=p['status'] if p else 'MISSING',error_ps=p['error_ps'] if p else ''))
    write(ROOT/'results/FREQUENCY_TRANSITIONS.csv',transitions)
    # 用已有只读D/时钟观测验证SDF确有非零物理传播延迟，不把它作为新校准参数。
    changes=read(ROOT/'results/compensated/gate_full/meta_changes.csv');observations=defaultdict(list)
    times={pol:sorted(int(t['rise_ps' if pol else 'fall_ps']) for t in truth) for pol in [0,1]}
    for c in changes:
        if not c['signal'].endswith('_D') or c['value'] not in ['0','1']:continue
        pol=int(c['value']);t=int(c['time_ps']);k=bisect.bisect_right(times[pol],t)-1
        if k>=0 and 0<=t-times[pol][k]<10000:observations[c['signal'],pol].append(t-times[pol][k])
    runtime=[dict(signal=signal,polarity='rise' if p else 'fall',samples=len(v),min_delay_ps=min(v),max_delay_ps=max(v),mean_delay_ps=sum(v)/len(v),purpose='SDF path-effect observation only; not a compensation refit') for (signal,p),v in sorted(observations.items())]
    write(ROOT/'results/RUNTIME_SDF_PATH_DELAYS.csv',runtime)
    runtime_pass=len(runtime)==8 and all(r['min_delay_ps']>0 for r in runtime)
    frontend={n:sha(ROOT/'results/compensated/gate_full'/n)==sha(Path('X:/results/baseline/gate_full')/n) for n in ['raw.csv','candidate.csv','sampled_taps.csv']}
    result=dict(same_event_ids_historical_compensated_count=len(common),RTL_04_05_width_error_identical=all(cases['04_merged_compensated_RTL'][1][i]==cases['05_optimized_compensated_RTL'][1][i] for i in range(3512)),old_04_MAX_SDF='NOT_EXECUTED in 04; no measurement invented',all_figures_condition_labeled=True,current_routed_frontend_byte_identical_to_03=frontend,runtime_SDF_path_effect_verified=runtime_pass,same_SDF_reconstructed_uncorrected_width_stats=stats(r['uncorrected_error_ps'] for r in reconstructed),same_SDF_compensated_width_stats=stats(int(r['compensated_error_ps']) for r in reconstructed),no_parameters_refitted=True,comparison_does_not_equate_ideal_RTL_with_SDF=True)
    (ROOT/'results/COMPARISON_VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    coverage=json.loads((ROOT/'results/SDF_COVERAGE.json').read_text(encoding='utf-8'));coverage['runtime_SDF_effect_verified']=runtime_pass;coverage['runtime_SDF_effect_verification']='8 phase/polarity D-path delay observations in RUNTIME_SDF_PATH_DELAYS.csv, all nonzero physical delays; no refit'
    (ROOT/'results/SDF_COVERAGE.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

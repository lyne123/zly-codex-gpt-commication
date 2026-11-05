"""复用上一轮事件统计方法；冻结关联延迟仅用于辨认事件，不修正测量值。"""
from pathlib import Path
from collections import Counter
import argparse,contextlib,csv,gzip,hashlib,importlib.util,json,math,re,shutil,statistics

ROOT=Path('W:/');OLD=Path('U:/')

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def stats(vals):
    vals=list(vals)
    return dict(n=len(vals),rmse_ps=math.sqrt(statistics.mean(x*x for x in vals)),bias_ps=statistics.mean(vals),std_ps=statistics.pstdev(vals)) if vals else dict(n=0,rmse_ps=None,bias_ps=None,std_ps=None)

def main():
    p=argparse.ArgumentParser();p.add_argument('dataset',choices=['local','full']);args=p.parse_args()
    case=ROOT/'results/compensated'/('gate_'+args.dataset)
    assert (case/'run_manifest.txt').exists(),'尚未完成仿真，禁止统计部分结果'
    spec=importlib.util.spec_from_file_location('frozen_analysis',OLD/'scripts/experiment.py');ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
    with (case/'analysis.log').open('w',encoding='utf-8') as f,contextlib.redirect_stdout(f):ref.analyze(case,ROOT/'inputs/frozen_baseline_association.json')
    summary=json.loads((case/'summary.json').read_text(encoding='utf-8'));truth=read(case/'truth.csv');aux=read(case/'aux_events.csv')
    unknown=[];counts={1:0,0:0}
    for row in aux:
        for polarity,key in [(1,'rise_slots'),(0,'fall_slots')]:
            try:counts[polarity]+=int(row[key]).bit_count()
            except ValueError:unknown.append(row)
    total=Counter();active=Counter();window=Counter();key_lines=[]
    windows=[(238600000,238900000),(241900000,242200000),(245200000,245500000)]
    shift=225280000 if args.dataset=='local' else 0
    with (case/'simulation.log').open(encoding='utf-8',errors='replace') as f:
        for line in f:
            if 'Timing violation in scope' not in line:continue
            m=re.search(r'scope (\S+) at time (\d+) ps \$(\w+)',line);assert m,line
            scope,t,check=m[1],int(m[2]),m[3]
            if 'mmcm_adv_inst' in scope and ('CLKOUT5' in line or 'CLKOUT6' in line):kind='MMCM_unused_outputs_model'
            elif 'u_tdl' in scope and 'thermo_q' in scope:kind='TDL_asynchronous_sampling'
            elif 'pwm_meta_reg' in scope:kind='AUX_first_stage_asynchronous_input'
            elif 'rst_sync' in scope:kind='reset_synchronizer'
            elif 'g_aux_4phase' in scope:kind='AUX_synchronous_requires_review'
            elif 'u_ila3/' in scope and ('shifted_data_in_reg[7][27]' in scope or 'G_NMU[4]' in scope):kind='ILA_asynchronous_debug_PWM'
            elif 'u_tdc_' in scope:kind='TDC_synchronous_requires_review'
            elif 'u_ila2/' in scope:kind='ILA2_nonfeedback'
            else:kind='other_requires_review'
            total[kind,check]+=1
            if t>=5000000:active[kind,check]+=1
            if any(a<=t+shift<=b for a,b in windows):
                window[kind,check]+=1
                if kind!='MMCM_unused_outputs_model':key_lines.append(line.rstrip())
    annotation='SDF backannotation was successful' in (case/'elaboration.log').read_text(encoding='utf-8',errors='replace')
    functional=summary['valid_matched_pulses']==len(truth) and summary['candidate_count']==summary['timestamp_count']==2*len(truth) and not summary['faults'] and not summary['business_errors'] and not summary['missing_rise_ids'] and not summary['missing_fall_ids'] and not summary['duplicate_rise_ids'] and not summary['duplicate_fall_ids'] and summary['fifo_sequence_equal']
    aux_pass=not unknown and counts[1]==counts[0]==len(truth)
    suspicious=sum(n for (kind,check),n in active.items() if kind in ['AUX_synchronous_requires_review','TDC_synchronous_requires_review','other_requires_review'])
    measurements=read(case/'measurements.csv')
    result=dict(dataset=args.dataset,expected_pulses=len(truth),expected_edges=2*len(truth),actual_edges=summary['timestamp_count'],correct_widths=summary['valid_matched_pulses'],
        missing_rise=summary['missing_rise_ids'],missing_fall=summary['missing_fall_ids'],duplicate_rise=summary['duplicate_rise_ids'],duplicate_fall=summary['duplicate_fall_ids'],mispairs=sum(not int(r['matched']) for r in measurements),
        aux_rises=counts[1],aux_falls=counts[0],aux_unknown_rows=len(unknown),annotation_success=annotation,functional_pass=functional and aux_pass,
        timing_checks='enabled',active_synchronous_warning_count=suspicious,all_observed_width_stats=stats(float(r['error_ps']) for r in measurements),
        full_set_stats=stats(float(r['error_ps']) for r in measurements) if functional else None,
        matched_only_stats=summary['groups']['all'],minimum_association_margin_ps=summary['minimum_association_margin_ps'],maximum_association_residual_ps=summary['maximum_association_residual_ps'],
        timing_warnings=[dict(kind=k,check=c,count=n,active_after_5us=active[k,c],in_target_windows=window[k,c]) for (k,c),n in sorted(total.items())],
        no_parameters_recalculated=True,association_reference='frozen prior independent calibration, used only for event IDs')
    (case/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (case/'key_window_warnings.log').write_text('\n'.join(key_lines)+'\n',encoding='utf-8')
    with (case/'simulation.log').open('rb') as src,gzip.open(case/'simulation.log.gz','wb') as dst:shutil.copyfileobj(src,dst)
    edges=read(case/'associated_timestamps.csv');recovery=[]
    for source_id in [2917,2918,2983,2984,3049,3050]:
        indices=[i for i,t in enumerate(truth) if int(t.get('source_event_id',t['pulse_id']))==source_id]
        if not indices:continue
        i=indices[0];r=[e for e in edges if int(e['pulse_id'])==i and int(e['type'])==1];f=[e for e in edges if int(e['pulse_id'])==i and int(e['type'])==0]
        widths=[m for m in measurements if int(m['pulse_id'])==i and int(m['matched'])]
        recovery.append(dict(source_event_id=source_id,local_index=i,rise_count=len(r),fall_count=len(f),correct_width_count=len(widths),pass_event=len(r)==len(f)==len(widths)==1))
    if recovery:
        with (case/'EVENT_RECOVERY.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(recovery[0]));w.writeheader();w.writerows(recovery)
    print(json.dumps({k:result[k] for k in ['dataset','expected_pulses','actual_edges','correct_widths','mispairs','aux_rises','aux_falls','functional_pass','active_synchronous_warning_count','all_observed_width_stats','minimum_association_margin_ps']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()

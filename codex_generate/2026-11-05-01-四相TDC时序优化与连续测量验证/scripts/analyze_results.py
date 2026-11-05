"""只分析已正常结束的批次，保留完整指标N/A和成功子集条件指标。"""
from pathlib import Path
import argparse
import bisect
import json
import re
import sys
from collections import Counter
import experiment as e

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'2026-11-04-02-四相TDC固定延迟补偿验证'

def categories(row):
    names=[row['case'],'all']
    if int(row['bank'])>=0:names.append('complete_frame')
    if int(row['header'])==0:names.append('header_5')
    if int(row['header'])==1:names.append('header_95')
    if int(row['bank'])>=0 and int(row['header'])<0:names.append('spwm_data')
    return names

def timing(folder):
    file=folder/'timing_summary.rpt'
    if (folder/'fresh_timing_summary.rpt').exists():file=folder/'fresh_timing_summary.rpt'
    if not file.exists():return None
    lines=file.read_text(errors='replace').splitlines()
    for i,line in enumerate(lines):
        if 'WNS(ns)' in line and 'TNS(ns)' in line:
            for x in lines[i+1:i+6]:
                values=x.split()
                if len(values)>=8 and re.fullmatch(r'-?\d+\.\d+',values[0]):
                    result=dict(wns_ns=float(values[0]),tns_ns=float(values[1]),setup_failing=int(values[2]),setup_endpoints=int(values[3]),whs_ns=float(values[4]),ths_ns=float(values[5]),hold_failing=int(values[6]),hold_endpoints=int(values[7]),wpws_ns=float(values[8]),tpws_ns=float(values[9]),pulse_width_failing=int(values[10]))
                    check_file=folder/'fresh_check_timing.rpt' if (folder/'fresh_check_timing.rpt').exists() else folder/'check_timing.rpt'
                    check=check_file.read_text(errors='replace')
                    result['constraint_checks']={k:int(v) for k,v in re.findall(r'checking (\w+) \((\d+)\)',check)}
                    bus_file=folder/'bus_skew_audit.rpt'
                    if not bus_file.exists():bus_file=folder/'bus_skew.rpt'
                    bus_slacks=[float(v) for v in re.findall(r'Slack \((?:MET|VIOLATED)\)\s*:\s*([-\d.]+)ns',bus_file.read_text(errors='replace'))] if bus_file.exists() else []
                    result['bus_skew_checked']=bool(bus_slacks)
                    result['bus_skew_min_slack_ns']=min(bus_slacks) if bus_slacks else None
                    result['synchronous_timing_pass']=result['wns_ns']>=0 and result['tns_ns']>=0 and result['whs_ns']>=0 and result['ths_ns']>=0 and result['wpws_ns']>=0 and not result['setup_failing'] and not result['hold_failing'] and not result['pulse_width_failing'] and all(result['constraint_checks'].get(k,1)==0 for k in ['no_clock','unconstrained_internal_endpoints','loops'])
                    result['synchronous_timing_pass']=result['synchronous_timing_pass'] and bool(bus_slacks) and min(bus_slacks)>=0
                    return result
    raise ValueError(f'无法解析时序表 {file}')

def utilization(folder):
    file=folder/'utilization.rpt'
    if not file.exists():return None
    text=file.read_text(errors='replace');result={}
    for key in ['Slice LUTs','LUT as Logic','LUT as Memory','Slice Registers','Block RAM Tile','CARRY4']:
        m=re.search(r'^\|\s*'+re.escape(key)+r'\s*\|\s*([\d,]+)',text,re.M)
        if m:result[key]=int(m[1].replace(',',''))
    return result

def analyze_case(phase,variant,level):
    case=ROOT/'results'/phase/variant/f'{level}_validation'
    if not (case/'run_manifest.txt').exists():return None
    meta=ROOT/'results/calibration'/phase/variant/level/'metadata.json'
    if phase=='original' and level=='gate':meta=ROOT/'inputs/old_calibration.json'
    if not meta.exists():return None
    saved=sys.stdout
    with (case/'analysis.log').open('w',encoding='utf-8') as f:
        sys.stdout=f
        try:e.analyze(case,meta)
        finally:sys.stdout=saved
    s=json.loads((case/'summary.json').read_text(encoding='utf-8'))
    truth=e.read_csv(case/'truth.csv');associated=e.read_csv(case/'associated_timestamps.csv');measurements=e.read_csv(case/'measurements.csv')
    for row in associated:
        row['pulse_id']=int(row['pulse_id']);row['type']=int(row['type'])
    counts={p:Counter(r['pulse_id'] for r in associated if r['type']==p) for p in (0,1)}
    errors=e.read_csv(case/'errors.csv')
    source_error_codes=[int(r['code']) for r in errors if r['kind']=='merge']
    fifo_error_codes=[int(r['code']) for r in e.read_csv(case/'error_fifo.csv')] if (case/'error_fifo.csv').exists() else None
    fifo=dict(result_sequence_equal=s['fifo_sequence_equal'],error_write_codes=source_error_codes,error_read_codes=fifo_error_codes,
        error_sequence_equal=source_error_codes==fifo_error_codes if fifo_error_codes is not None else None,
        overflow_observation_cycles=sum(r['kind']=='overflow' for r in errors),unknown_observation_rows=sum('unknown' in r['kind'] for r in errors))
    (case/'fifo_check.json').write_text(json.dumps(fifo,indent=2),encoding='utf-8')
    rows=[]
    for group,g in s['groups'].items():
        ids={int(r['pulse_id']) for r in truth if group in categories(r)}
        selected=[r for r in measurements if int(r['pulse_id']) in ids]
        row=dict(phase=phase,variant=variant,level=level,test=group,expected_pulses=len(ids),expected_rises=len(ids),expected_falls=len(ids),expected_edges=2*len(ids),
            actual_rises=sum(counts[1][i] for i in ids),actual_falls=sum(counts[0][i] for i in ids),
            missing_rises=sum(not counts[1][i] for i in ids),missing_falls=sum(not counts[0][i] for i in ids),
            duplicate_rises=sum(max(0,counts[1][i]-1) for i in ids),duplicate_falls=sum(max(0,counts[0][i]-1) for i in ids),
            output_widths=len(selected),correct_pairs=g['matched_unique_n'],mispairs=sum(not int(r['matched']) for r in selected),
            complete=g['complete'],valid_rate=g['matched_unique_n']/len(ids),rmse_ps=g['rmse_ps'] if g['complete'] else 'N/A',
            bias_ps=g['bias_ps'] if g['complete'] else 'N/A',std_ps=g['std_ps'] if g['complete'] else 'N/A',max_abs_ps=g['max_abs_ps'] if g['complete'] else 'N/A',
            conditional_rmse_ps=g['rmse_ps'],conditional_bias_ps=g['bias_ps'],conditional_std_ps=g['std_ps'],conditional_max_abs_ps=g['max_abs_ps'],
            result_fifo_sequence_equal=fifo['result_sequence_equal'],error_fifo_sequence_equal=fifo['error_sequence_equal'],overflow_run_observation_cycles=fifo['overflow_observation_cycles'])
        rows.append(row)
    e.write_csv(case/'test_metrics.csv',rows)
    return dict(phase=phase,variant=variant,level=level,summary=s,fifo=fifo,metrics=rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');a=p.parse_args()
    cases=[]
    for phase in ['original','optimized']:
        for variant in ['baseline','compensated']:
            for level in ['rtl','gate']:
                value=analyze_case(phase,variant,level)
                if value:cases.append(value)
    if a.final:assert len(cases)==8,f'仅{len(cases)}/8完整对照批次'
    e.write_csv(ROOT/'results/ALL_CASE_METRICS.csv',(r for c in cases for r in c['metrics']))
    by={(c['phase'],c['variant'],c['level']):c for c in cases}
    comparison=[]
    for name in sorted({r['test'] for c in cases for r in c['metrics']}):
        row={'test':name}
        for phase in ['original','optimized']:
            for variant in ['baseline','compensated']:
                c=by.get((phase,variant,'gate'))
                g=c['summary']['groups'][name] if c else None
                tag=f'{phase}_{variant}'
                for metric in ['rmse_ps','bias_ps','std_ps','max_abs_ps']:
                    row[tag+'_'+metric]=g[metric] if g and g['complete'] else 'N/A'
                    row[tag+'_conditional_'+metric]=g[metric] if g else 'NOT_EXECUTED'
                row[tag+'_correct_pairs']=g['matched_unique_n'] if g else 'NOT_EXECUTED'
                row[tag+'_expected_n']=g['expected_n'] if g else 'NOT_EXECUTED'
        before=row['original_compensated_rmse_ps'];after=row['optimized_compensated_rmse_ps']
        row['compensated_rmse_change_ratio']=(after-before)/before if isinstance(before,(int,float)) and isinstance(after,(int,float)) and before else 'N/A'
        comparison.append(row)
    e.write_csv(ROOT/'RMS_COMPARISON.csv',comparison)
    static={}
    for phase,folder in [('original','original_inspection'),('optimized','optimized')]:
        for variant in ['baseline','compensated']:
            path=ROOT/'results'/folder/variant
            static[f'{phase}_{variant}']={'timing':timing(path),'resources':utilization(path)}
    summary=dict(completed_cases=len(cases),total_required_cases=8,static=static,
        cases=[{k:v for k,v in c.items() if k!='metrics'} for c in cases])
    (ROOT/'results/analysis_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    for c in cases:print(c['phase'],c['variant'],c['level'],c['summary']['valid_matched_pulses'],'/',c['summary']['expected_pulses'],'missing',len(c['summary']['missing_rise_ids']),len(c['summary']['missing_fall_ids']),'fifo',c['fifo']['result_sequence_equal'],c['fifo']['error_sequence_equal'])
    print('completed_cases',len(cases),'of 8')

if __name__=='__main__':main()

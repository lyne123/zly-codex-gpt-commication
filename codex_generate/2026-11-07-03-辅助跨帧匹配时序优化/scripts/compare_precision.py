"""分别报告全部有效结果与共同事件ID，不用丢失事件改变样本群制造改善。"""
from pathlib import Path
import csv,json
from analyze_sdf import read,stats,write
TASK=Path(__file__).resolve().parents[1]
before=TASK/'results/sdf/baseline/full';after=TASK/'results/sdf/corrected/full'
bs=json.loads((before/'SUMMARY.json').read_text(encoding='utf-8'));cs=json.loads((after/'SUMMARY.json').read_text(encoding='utf-8'))
b={int(r['event_id']):r for r in read(before/'PULSE_RESULTS.csv') if r['status']=='MATCHED'}
c={int(r['event_id']):r for r in read(after/'PULSE_RESULTS.csv') if r['status']=='MATCHED'}
common=sorted(set(b)&set(c));rows=[]
for population,keys in [('all_valid',None),('same_input_common_ID',common)]:
    for label,data in [('baseline',b),('corrected',c)]:
        selected=list(data.values()) if keys is None else [data[i] for i in keys]
        for group in ['all']+list(dict.fromkeys(r['case'] for r in selected)):
            values=[int(r['error_ps']) for r in selected if group=='all' or r['case']==group]
            rows.append(dict(population=population,version=label,group=group,**stats(values)))
write(TASK/'results/PRECISION_COMPARISON.csv',rows,['population','version','group','n','bias_ps','rmse_ps','std_sample_ps','std_population_ps','max_abs_ps'])
result=dict(baseline_valid=bs['correct_pairs'],corrected_valid=cs['correct_pairs'],common_event_count=len(common),
    baseline_missing=bs['missing_rise_ids']+bs['missing_fall_ids'],corrected_missing=cs['missing_rise_ids']+cs['missing_fall_ids'],
    parameters_refitted=False,outliers_removed=False,reference='同一冻结3512脉冲输入；Baseline为实际AD23生产DCP，不用旧AF20报告代替',metrics=rows)
(TASK/'results/PRECISION_COMPARISON.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='metrics'},ensure_ascii=False,indent=2))

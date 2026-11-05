"""按真实事件编号连接八组结果，完整保留漏沿、错配和逐事件误差。"""
from pathlib import Path
from collections import defaultdict
import json
import experiment as e

ROOT=Path(__file__).resolve().parents[1]

def main():
    records=[];anomalies=[]
    old_ids={2917,2918,2983,2984,3050}
    for phase in ['original','optimized']:
        for variant in ['baseline','compensated']:
            for level in ['rtl','gate']:
                case=ROOT/'results'/phase/variant/f'{level}_validation'
                assert (case/'summary.json').exists(),str(case)
                edges=defaultdict(list);widths=defaultdict(list)
                for row in e.read_csv(case/'associated_timestamps.csv'):edges[int(row['pulse_id']),int(row['type'])].append(row)
                for row in e.read_csv(case/'measurements.csv'):widths[int(row['pulse_id'])].append(row)
                errors=e.read_csv(case/'errors.csv')
                for truth in e.read_csv(case/'truth.csv'):
                    i=int(truth['pulse_id']);r=edges[i,1];f=edges[i,0];w=widths[i]
                    correct=[x for x in w if int(x['matched'])]
                    item=dict(phase=phase,variant=variant,level=level,event_id=i,test=truth['case'],bank=truth['bank'],channel=truth['channel'],header=truth['header'],
                        rise_ps=truth['rise_ps'],fall_ps=truth['fall_ps'],true_width_ps=truth['true_width_ps'],
                        rise_count=len(r),fall_count=len(f),width_count=len(w),correct_width_count=len(correct),mispair_count=len(w)-len(correct),
                        measured_widths_ps=';'.join(x['measured_width_ps'] for x in w),rise_input_ids=';'.join(x['rise_input_id'] for x in w),fall_input_ids=';'.join(x['fall_input_id'] for x in w),
                        correct_errors_ps=';'.join(x['error_ps'] for x in correct),rise_selected_indices=';'.join(x['index'] for x in r),fall_selected_indices=';'.join(x['index'] for x in f),
                        rise_codes=';'.join(x['code'] for x in r),fall_codes=';'.join(x['code'] for x in f),
                        association_margin_min_ps=min([float(x['association_margin_ps']) for x in r+f],default='N/A'))
                    item['complete']=len(r)==len(f)==len(w)==len(correct)==1
                    records.append(item)
                    if not item['complete'] or i in old_ids:
                        lo=int(truth['rise_ps']);hi=int(truth['fall_ps'])+70000
                        nearby=[x for x in errors if lo<=int(x['time_ps'])<=hi]
                        anomalies.append(dict(item,nearby_errors=json.dumps(nearby,ensure_ascii=False),trace_file=str((case/'anomaly_pipeline_trace.csv').relative_to(ROOT))))
    e.write_csv(ROOT/'results/EVENT_COMPARISON.csv',records)
    e.write_csv(ROOT/'results/ANOMALY_EVENT_REVIEW.csv',anomalies)
    print('事件对照行数',len(records),'重点事件行数',len(anomalies))

if __name__=='__main__':main()

"""仅作因果诊断：检查漏沿附近的原始四相有效时间信息，不筛除RMS样本。"""
from pathlib import Path
import json
from collections import defaultdict
import experiment as e

root=Path(__file__).resolve().parents[1]
case=root/'results/optimized/baseline/gate_validation'
truth=e.read_csv(case/'truth.csv')
raw=e.numeric(case/'raw.csv')
meta=json.loads((root/'results/calibration/optimized/baseline/gate/metadata.json').read_text(encoding='utf-8'))
params={(r['sel_index'],int(r['polarity']=='rise')):r['offset_ps'] for r in meta['parameters']}
latencies=defaultdict(list);residuals=defaultdict(list)
for row in e.numeric(root/'results/calibration/optimized/baseline/gate/observations.csv'):
    key=row['sel_index'],row['polarity']
    latencies[key].append(row['time_ps']-row['true_time_ps'])
    residuals[key].append(row['error_ps']-params[key])
summary=json.loads((case/'summary.json').read_text(encoding='utf-8'))
rows=[]
for p,missing in [(1,summary['missing_rise_ids']),(0,summary['missing_fall_ids'])]:
    for event_id in missing:
        true=int(truth[event_id]['rise_ps' if p else 'fall_ps'])
        found=[]
        for frame in raw:
            if not 12000<=frame['time_ps']-true<=32000:continue
            for i in range(4):
                if not frame['mask']&(1<<i) or ((frame['polarity']>>(2*i))&3)!=(3 if p else 2):continue
                code=(frame['codes']>>(8*i))&255;tap=code if p else 64-code
                measured=(((frame['coarse']+6)%1024)*2000+(i+1)*500-tap*10-params[i,p])%e.MODULO
                error=e.circular(measured-(true-meta['epoch_ps'])%e.MODULO)
                found.append(dict(raw_time_ps=frame['time_ps'],index=i,code=code,error_ps=error))
        best=min(found,key=lambda r:abs(r['error_ps'])) if found else None
        envelope=max(abs(x) for i in range(4) for x in residuals[i,p])
        rows.append(dict(event_id=event_id,polarity='rise' if p else 'fall',true_time_ps=true,valid_raw_channel_samples_in_window=len(found),
            best_raw_error_ps=best['error_ps'] if best else 'NONE',best_raw_time_ps=best['raw_time_ps'] if best else 'NONE',
            calibration_max_abs_residual_ps=envelope,any_raw_inside_calibration_envelope=any(abs(r['error_ps'])<=envelope for r in found),
            all_raw_samples=json.dumps(found)))
e.write_csv(root/'results/MISSING_RAW_EDGE_REVIEW.csv',rows)
print(json.dumps(rows,ensure_ascii=False))

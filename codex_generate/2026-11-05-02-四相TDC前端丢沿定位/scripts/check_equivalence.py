"""逐字段验证短窗口与冻结完整仿真的对应窗口，不容忍采样差异。"""
from pathlib import Path
import csv
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'2026-11-05-01-四相TDC时序优化与连续测量验证'
WINDOWS=[(238600000,238900000),(241900000,242200000),(245200000,245500000)]
FILES=['raw.csv','candidate.csv','timestamps.csv','widths.csv','errors.csv','fifo.csv','error_fifo.csv','sampled_taps.csv','anomaly_pipeline_trace.csv']

def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return [r for r in csv.DictReader(f) if any(a<=int(r['time_ps'])<=b for a,b in WINDOWS)]

def main():
    result={}
    case=ROOT/'results/short_baseline'
    for name in FILES:
        frozen=rows(OLD/'results/optimized/baseline/gate_validation'/name)
        local=rows(case/name)
        diff=[dict(row=i,original=a,short=b) for i,(a,b) in enumerate(zip(frozen,local)) if a!=b]
        result[name]=dict(original_rows=len(frozen),short_rows=len(local),equal=frozen==local,first_differences=diff[:3])
    passed=all(x['equal'] for x in result.values())
    (ROOT/'results/SHORT_WINDOW_EQUIVALENCE.json').write_text(json.dumps(dict(pass_all_fields=passed,windows_absolute_ps=WINDOWS,comparisons=result),ensure_ascii=False,indent=2),encoding='utf-8')
    # 导出窗口对应关系，CSV 数据保持观察原值，只增补事件编号。
    with (case/'frontend_signals.csv').open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        with (ROOT/'EVENT_TRACE.csv').open('w',encoding='utf-8-sig',newline='') as out:
            w=csv.DictWriter(out,fieldnames=['event_ids']+reader.fieldnames);w.writeheader()
            for r in reader:
                t=int(r['time_ps'])
                r['event_ids']=next(ids for (a,b),ids in zip(WINDOWS,['2917;2918','2983;2984','3049;3050']) if a<=t<=b)
                w.writerow(r)
    baseline=json.loads((ROOT/'inputs/SOURCE_SHA256.json').read_text(encoding='utf-8'))
    checks={}
    for name,meta in baseline.items():
        p=Path(name)
        with p.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
        checks[name]=digest==meta['sha256']
    (ROOT/'results/SOURCE_UNCHANGED.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(equivalent=passed,comparisons={n:[v['original_rows'],v['short_rows'],v['equal']] for n,v in result.items()},source_unchanged=all(checks.values())),ensure_ascii=False,indent=2))
    if not passed: raise SystemExit('短窗口不等价，不得据此下完整实验根因结论。')

if __name__=='__main__':main()

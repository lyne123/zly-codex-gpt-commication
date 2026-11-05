"""确认新设计局部窗口与同一新设计完整仿真一致，保留全部比较结果。"""
from pathlib import Path
import csv,json
ROOT=Path('W:/results/baseline')
WINDOWS=[(238600000,238900000),(241900000,242200000),(245200000,245500000)]
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:
        result=[]
        for r in csv.DictReader(f):
            if any(lo<=int(r['time_ps'])<=hi for lo,hi in WINDOWS):
                r.pop('local_time_ps',None);result.append(r)
        return sorted(result,key=lambda r:tuple(sorted(r.items())))
def main():
    names=['raw.csv','candidate.csv','timestamps.csv','widths.csv','errors.csv','fifo.csv','error_fifo.csv','sampled_taps.csv','anomaly_pipeline_trace.csv','aux_events.csv','aux_windows.csv','meta_capture.csv','meta_changes.csv']
    compared={}
    for name in names:
        short=read(ROOT/'gate_local'/name);full=read(ROOT/'gate_full'/name)
        compared[name]=dict(local_rows=len(short),full_rows=len(full),all_fields_equal=short==full)
    result=dict(pass_all=all(x['all_fields_equal'] for x in compared.values()),time_translation_ps=225280000,excluded_metadata_column='local_time_ps',comparisons=compared)
    (Path('W:/results')/'SHORT_FULL_EQUIVALENCE.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
    assert result['pass_all'],'局部和完整窗口不一致，禁止宣称局部等价'
if __name__=='__main__':main()

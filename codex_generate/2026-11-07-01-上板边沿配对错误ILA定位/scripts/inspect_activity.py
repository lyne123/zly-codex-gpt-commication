"""按Vivado原始CSV的Radix行读取真实活动快照，不把快照统计当作正式精度验收。"""
from pathlib import Path
from collections import Counter
import csv,json,statistics,sys

def read_capture(path):
    if not path.exists():return []
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);radix=next(reader)
        rows=[r for r in reader if r['Sample in Buffer'].isdigit()]
    bases={'HEX':16,'UNSIGNED':10,'SIGNED':10,'BIN':2,'BINARY':2,'OCTAL':8}
    return [{k:int(v,bases.get(radix.get(k,''),10)) for k,v in r.items()} for r in rows]

def column(row,prefix):
    return next(k for k in row if k.startswith(prefix))

def main():
    folder=Path(sys.argv[1]).resolve();result={'capture_kind':'IMMEDIATE_ACTIVITY_ONLY_NOT_ERROR_TRIGGER'}
    rows=read_capture(folder/'u_ila3_ACTIVITY.csv')
    a={'sample_count':len(rows),'clock_domain_MHz':100}
    if rows:
        levels=[r['pwm_in_IBUF'] for r in rows]
        rises=[i for i in range(1,len(rows)) if levels[i] and not levels[i-1]]
        errors=Counter(r[column(r,'error_code_100m')] for r in rows if r['error_valid_100m'])
        widths=[r[column(r,'pulse_width_ps_100m')] for r in rows if r['pulse_width_valid_100m']]
        a.update(input_transitions=sum(x!=y for x,y in zip(levels,levels[1:])),
            input_high_fraction=sum(levels)/len(levels),input_rises=len(rises),
            rise_period_clock_histogram=dict(Counter(y-x for x,y in zip(rises,rises[1:]))),
            valid_width_outputs=len(widths),error_events=dict(errors))
        if widths:a.update(mean_width_ps=statistics.mean(widths),min_width_ps=min(widths),max_width_ps=max(widths))
    result['ILA100M']=a
    rows=read_capture(folder/'u_ila_edge_debug_ACTIVITY.csv')
    a={'sample_count':len(rows),'clock_domain_MHz':500}
    if rows:
        ctrl=[r[column(r,'debug_control_q')] for r in rows]
        cycles=[r[column(r,'debug_cycle_q')] for r in rows]
        counts=[r[column(r,'debug_counts_q')] for r in rows]
        a.update(reset_released_samples=sum((v>>20)&1 for v in ctrl),
            mmcm_locked_samples=sum((v>>21)&1 for v in ctrl),
            pipeline_ready_samples=sum((v>>22)&1 for v in ctrl),
            timestamp_rises=sum(bool(v&(1<<12)) and bool(v&(1<<13)) for v in ctrl),
            timestamp_falls=sum(bool(v&(1<<12)) and not bool(v&(1<<13)) for v in ctrl),
            duplicate_rise_pulses=sum(v&1 for v in ctrl),orphan_fall_pulses=sum((v>>1)&1 for v in ctrl),
            A_counter_first_last=[counts[0]&0xffffffff,counts[-1]&0xffffffff],
            B_counter_first_last=[counts[0]>>32,counts[-1]>>32],
            cycle_increment_histogram=dict(Counter((y-x)%(1<<32) for x,y in zip(cycles,cycles[1:]))))
    result['ILA500M']=a
    (folder/'ACTIVITY_SUMMARY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

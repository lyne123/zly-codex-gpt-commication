"""按原事件时间列出实际观察值，用于人工审查首次丢失位置。"""
from pathlib import Path
import csv
import json

ROOT=Path(__file__).resolve().parents[1]

def main():
    case=ROOT/'results/short_baseline'
    with (ROOT/'inputs/EDGE_TIME_MAPPING.csv').open(encoding='utf-8-sig') as f: pulses={int(r['event_id']):r for r in csv.DictReader(f)}
    with (case/'signal_changes.csv').open(encoding='utf-8-sig') as f: changes=list(csv.DictReader(f))
    with (case/'aux_capture.csv').open(encoding='utf-8-sig') as f: captures=list(csv.DictReader(f))
    selected=[]
    for event in [2917,2918,2983,2984,3049,3050]:
        pol='fall' if event%2 else 'rise'
        when=int(pulses[event][pol+'_absolute_ps'])
        print(f'\nEVENT {event} {pol} input={when}')
        lo,hi=when-2500,when+30000
        for row in captures:
            if row['stage']=='pwm_meta' and lo<=int(row['time_ps'])<=when+6000:print('CAPTURE',row)
        for row in changes:
            name=row['signal'];t=int(row['time_ps'])
            if not lo<=t<=hi:continue
            if name.startswith('pwm_') and any(name.endswith('_'+x) for x in ['C','C_dly','Q']):continue
            if name.endswith('_carry') or name.endswith('_code_raw') or name.endswith('_code_q') or name.endswith('_code_in_range'):continue
            if name in ['sync_valid','frame_ready'] or name.endswith('_ready'):continue
            selected.append(dict(event_id=event,edge_ps=when,delta_ps=t-when,**row))
            print(t,t-when,name,row['value_hex'])
    with (ROOT/'results/KEY_TRANSITIONS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['event_id','edge_ps','delta_ps','time_ps','local_time_ps','signal','value_hex']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(selected)

if __name__=='__main__':main()

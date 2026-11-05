"""保留 SDF 注释及全部告警证据，单列异常窗口；不关闭任何检查。"""
from pathlib import Path
from collections import Counter
import csv
import gzip
import hashlib
import json
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]
SHIFT=225280000
WINDOWS=[(238600000,238900000),(241900000,242200000),(245200000,245500000)]

def main():
    case=ROOT/'results/short_baseline'
    elaboration=(ROOT/'build/short_baseline/elaborate.log').read_text(errors='replace')
    counts=Counter();active=Counter();window=[];checks=[];startup=[];done=False
    with (case/'simulation.log').open(errors='replace') as f:
        for line in f:
            done=done or 'TDC_SIM_DONE' in line
            if 'Timing violation in scope' not in line:continue
            m=re.search(r'scope (\S+) at time (\d+) ps \$(\w+)',line)
            if not m:raise ValueError(line)
            scope,local,check=m[1],int(m[2]),m[3]
            if 'mmcm_adv_inst' in scope and ('CLKOUT5' in line or 'CLKOUT6' in line):category='MMCM_unused_CLKOUT5_6_model'
            elif 'u_tdl' in scope and 'thermo_q' in scope:category='TDL_asynchronous_sampling'
            elif 'pwm_meta' in scope or 'pwm_sync' in scope:category='PWM_asynchronous_synchronizer'
            elif 'rst_sync' in scope:category='reset_synchronizer'
            elif 'u_ila3/' in scope and ('shifted_data_in_reg[7][27]' in scope or 'G_NMU[4]' in scope):category='ILA_asynchronous_PWM_debug_capture'
            elif 'u_tdc_' in scope:category='synchronous_TDC_digital_requires_review'
            else:category='other_requires_review'
            counts[category,check]+=1
            if local>=5000000:active[category,check]+=1
            if category=='synchronous_TDC_digital_requires_review':startup.append(dict(local_time_ps=local,scope=scope,check=check))
            if any(a<=local+SHIFT<=b for a,b in WINDOWS):
                window.append(dict(time_ps=local+SHIFT,local_time_ps=local,category=category,check=check,scope=scope))
                if category!='MMCM_unused_CLKOUT5_6_model':checks.append(line.rstrip())
    with (ROOT/'results/WINDOW_TIMING_WARNINGS.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['time_ps','local_time_ps','category','check','scope']);w.writeheader();w.writerows(window)
    (ROOT/'logs/key_timing_warnings.log').write_text('\n'.join(checks)+'\n',encoding='utf-8')
    summary=dict(annotation_success='SDF backannotation was successful' in elaboration,
                 annotation_messages=[l for l in elaboration.splitlines() if 'SDF' in l],
                 normal_finish=done,timing_checks='enabled',delay_corner='MAXIMUM',simulator='Vivado XSim 2022.2',
                 counts=[dict(category=c,check=k,count=v,after_5us_count=active[c,k]) for (c,k),v in sorted(counts.items())],
                 synchronous_check_details=startup,
                 window_counts=dict(Counter(r['category'] for r in window)))
    (ROOT/'results/RUN_AUDIT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copyfile(ROOT/'build/short_baseline/elaborate.log',ROOT/'logs/elaborate.log')
    # 压缩副本不替代原日志；源文件和所有告警原文继续保留本地。
    with (case/'simulation.log').open('rb') as src, gzip.open(ROOT/'logs/simulation.log.gz','wb') as dst:shutil.copyfileobj(src,dst)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

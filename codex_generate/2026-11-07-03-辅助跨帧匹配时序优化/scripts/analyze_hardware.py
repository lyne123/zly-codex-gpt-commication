"""复用原ILA解析器，按采集顺序统计前10000有效输出；所有原始和额外数据保留。"""
from pathlib import Path
from collections import Counter
import csv,hashlib,json,re,shutil,statistics
from ila_csv import read_capture

TASK=Path(__file__).resolve().parents[1]
WORK=TASK.parents[1]/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
out=TASK/'results/hardware_validation_10MHz_50'
out.mkdir(exist_ok=True)
source=WORK/'hardware_03';evidence=TASK/'results/hardware_03'
for p in source.iterdir():
    if p.suffix in ['.csv','.txt','.log','.jou','.tcl']:shutil.copy2(p,evidence/p.name)
samples=[];errors=[];captures=[];totals=Counter();new_count=0
for folder in ['hardware_02','hardware_03']:
    for order,p in enumerate(sorted((TASK/'results'/folder).glob('ACTIVITY_*.csv'),key=lambda p:int(p.stem.split('_')[-1]))):
        r=read_capture(p);assert r['counts']['buffer_rows']==2048,p
        cid=len(captures);totals.update(r['counts'])
        captures.append(dict(capture_id=cid,file=p.relative_to(TASK).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),**r['counts']))
        for row in r['samples']:samples.append(dict(sample_idx=len(samples),capture_id=cid,**row))
        errors.extend(dict(capture_id=cid,**row) for row in r['errors'])
        if folder=='hardware_03':new_count+=r['counts']['valid_measurements']
assert len(samples)>=10000,'不足10000，不宣称完成'
status=(evidence/'HARDWARE_STATUS.txt').read_text(encoding='utf-8')
assert int(re.search(r'^valid_measurements=(\d+)$',status,re.M)[1])==new_count,'Tcl计数与独立解析结果不同'
cutoff=samples[9999];primary=samples[:10000]
for row in samples:row['include_in_primary']=int(row['sample_idx']<10000)
for row in errors:row['include_in_primary']=int((row['capture_id'],row['buffer_sample_idx'])<=(cutoff['capture_id'],cutoff['buffer_sample_idx']))
selected=[row for row in errors if row['include_in_primary']]
widths=[row['pulse_width_ps'] for row in primary];mean=statistics.mean(widths)
def save(name,rows,fields):
    with (out/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
save('SAMPLES.csv',samples,['sample_idx','capture_id','buffer_sample_idx','pulse_width_ps','include_in_primary'])
save('ERROR_EVENTS.csv',errors,['capture_id','buffer_sample_idx','error_code','include_in_primary'])
save('CAPTURES.csv',captures,list(captures[0]))
codes=Counter(str(row['error_code']) for row in selected)
summary=dict(BIT_sha256='59f1630048ade43ec5c0d7560c1e756ba664421e83e53c84028ca4956a61f523',
    state='Corrected',input_frequency_MHz_user_confirmed=10,input_duty_percent_user_confirmed=50,
    nominal_width_ps=50000,reference_width_ps=None,primary_valid=10000,total_valid_preserved=len(samples),
    extra_valid_preserved=len(samples)-10000,counts_all=dict(totals),primary_error_codes=dict(codes),
    all_error_codes=dict(Counter(str(row['error_code']) for row in errors)),
    repeat_rise=int(codes['1']),orphan_fall=int(codes['2']),range_error=int(codes['3']),
    mean_width_ps=mean,sample_STD_ps=statistics.stdev(widths),
    Bias_vs_setpoint_ps=mean-50000,RMSE_vs_setpoint_ps=(statistics.mean((x-50000)**2 for x in widths))**0.5,
    MaxAbs_vs_setpoint_ps=max(abs(x-50000) for x in widths),minimum_width_ps=min(widths),maximum_width_ps=max(widths),
    absolute_Bias=None,zero_pairing_errors_requirement_met=not selected,
    previous_600_valid_and_14_errors_included=True,no_outlier_removal=True,
    per_pulse_error_association_available=False,FIFO_overflow_observable=False,
    inter_window_input_events_unobserved=True,input_event_count_available=False,
    full_AB_completed=False,programmed_once=True,flash_programmed=False,
    selection_rule='前10000个valid且范围内可读的输出，按采集顺序；截止第10000输出的全部错误计入，剩余数据保留')
(out/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
for directory in [TASK/'results/hardware_01',TASK/'results/hardware_02',evidence,out]:
    (directory/'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in sorted(directory.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))

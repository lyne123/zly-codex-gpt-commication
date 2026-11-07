"""复用ILA解析器，保留全部原始记录，统计前10000个有效输出及同期错误。"""
from pathlib import Path
from collections import Counter
import argparse,csv,json,re,shutil,statistics
from ila_csv import read_capture,number,digest,write_csv

TASK=Path(__file__).resolve().parents[1]
WORK=TASK.parents[1]/'codex_generate/.vivado_work/tdc_noaux_20261107_04'
parser=argparse.ArgumentParser()
parser.add_argument('--attempt',required=True)
parser.add_argument('--archived',action='store_true',help='只读取归档CSV，不依赖本机原生运行目录')
args=parser.parse_args()
assert re.fullmatch(r'hardware_\d+',args.attempt),'只允许本任务采集目录'
evidence=TASK/'results'/args.attempt
source=evidence if args.archived else WORK/args.attempt
meta=json.loads((evidence/'PROGRAM_INPUT.json').read_text(encoding='utf-8'))
status=(source/'HARDWARE_STATUS.txt').read_text(encoding='utf-8')
for expected in ['programming_completed=1','configuration_verified=1','attempt_status=COMPLETED']:
    assert expected in status,'下载或采集未完成：'+expected
for name in ['NoAux.bit','NoAux.ltx']:
    assert meta['files'][name]['sha256']==digest(TASK/'implementation'/name)
    if not args.archived:assert digest(source/name)==meta['files'][name]['sha256']
for p in source.iterdir():
    if not args.archived and p.is_file() and p.suffix in ['.csv','.txt','.log','.jou','.tcl','.json']:
        shutil.copy2(p,evidence/p.name)
out=TASK/'results/hardware_validation_10MHz_50';out.mkdir(exist_ok=True)
samples=[];errors=[];invalid=[];captures=[];totals=Counter();periods=[];pwm_counts=Counter()
paths=sorted(evidence.glob('ACTIVITY_*.csv'),key=lambda p:int(p.stem.split('_')[-1]))
for cid,p in enumerate(paths):
    r=read_capture(p);assert r['counts']['buffer_rows']==2048,p
    assert r['error_stream_available'],'缺少独立错误流，不能报告零错误'
    totals.update(r['counts'])
    captures.append(dict(capture_id=cid,file=p.relative_to(TASK).as_posix(),sha256=digest(p),**r['counts']))
    for row in r['samples']:samples.append(dict(sample_idx=len(samples),capture_id=cid,**row))
    errors.extend(dict(capture_id=cid,**row) for row in r['errors'])
    invalid.extend(dict(capture_id=cid,**row) for row in r['invalid'])
    # 100MHz采样仅复核输入活动、粗周期和占空比，不作为示波器参考值。
    with p.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.reader(f);header=next(reader);radix=next(reader)
        indexes=[i for i,n in enumerate(header) if n=='pwm_in_IBUF']
        assert len(indexes)==1,'PWM探针缺失或不唯一'
        pi=indexes[0];levels=[number(row[pi],radix[pi]) for row in reader if row]
    pwm_counts.update(str(x) for x in levels)
    rises=[i for i in range(1,len(levels)) if levels[i-1]==0 and levels[i]==1]
    periods.extend(b-a for a,b in zip(rises,rises[1:]))
goal=meta['target_valid'];assert len(samples)>=goal,'有效输出不足，不宣称完成'
assert len(samples)==int(re.search(r'^valid_measurements=(\d+)$',status,re.M)[1]),'Tcl和Python计数不一致'
assert len(paths)==int(re.search(r'^ILA_activity_windows=(\d+)$',status,re.M)[1])
cutoff=samples[goal-1]
for row in samples:row['include_in_primary']=int(row['sample_idx']<goal)
for row in errors:row['include_in_primary']=int((row['capture_id'],row['buffer_sample_idx'])<=(cutoff['capture_id'],cutoff['buffer_sample_idx']))
selected=[row for row in errors if row['include_in_primary']]
codes=Counter(str(row['error_code']) for row in selected)
widths=[row['pulse_width_ps'] for row in samples[:goal]];nominal=meta['nominal_width_ps']
write_csv(out/'SAMPLES.csv',['sample_idx','capture_id','buffer_sample_idx','pulse_width_ps','include_in_primary'],samples)
write_csv(out/'ERROR_EVENTS.csv',['capture_id','buffer_sample_idx','error_code','include_in_primary'],errors)
write_csv(out/'INVALID_RECORDS.csv',['capture_id','buffer_sample_idx','reason','raw_width'],invalid)
write_csv(out/'CAPTURES.csv',list(captures[0]),captures)
summary=dict(BIT_sha256=meta['files']['NoAux.bit']['sha256'],state='NoAux',ENABLE_AUX_CONFIRM=0,
    source_commit=meta['source_commit'],attempt=args.attempt,input_condition_source=meta['condition_source'],
    nominal_frequency_MHz=meta['input_frequency_MHz'],nominal_duty_percent=meta['input_duty_percent'],
    nominal_width_ps=nominal,reference_width_ps=None,primary_valid=goal,total_valid_preserved=len(samples),
    extra_valid_preserved=len(samples)-goal,counts_all=dict(totals),primary_error_codes=dict(codes),
    all_error_codes=dict(Counter(str(row['error_code']) for row in errors)),
    repeat_rise=codes['1'],orphan_fall=codes['2'],range_error=codes['3'],
    mean_width_ps=statistics.mean(widths),sample_STD_ps=statistics.stdev(widths),
    MAE_vs_setpoint_ps=statistics.mean(abs(x-nominal) for x in widths),
    RMSE_vs_setpoint_ps=statistics.mean((x-nominal)**2 for x in widths)**0.5,
    MaxAbs_vs_setpoint_ps=max(abs(x-nominal) for x in widths),
    minimum_width_ps=min(widths),maximum_width_ps=max(widths),absolute_accuracy_available=False,
    zero_pairing_errors_requirement_met=not selected,no_outlier_removal=True,
    per_pulse_error_association_available=False,FIFO_overflow_observable=False,
    inter_window_input_events_unobserved=True,input_event_count_available=False,
    full_AB_completed=False,FPGA_programming_verified=True,flash_programmed=False,
    PWM_100MHz_observation=dict(level_counts=dict(pwm_counts),period_sample_counts=dict(Counter(periods)),
        median_period_ps=statistics.median(periods)*10000 if periods else None,
        high_fraction=pwm_counts['1']/(pwm_counts['0']+pwm_counts['1']) if pwm_counts['0']+pwm_counts['1'] else None,
        note='粗采样用于复核输入活动，不能排除短毛刺或提供校准脉宽参考'),
    selection_rule='采集顺序前10000个valid且范围内可读的输出；同期全部错误计入；额外、无效、原始记录全部保留')
(out/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
for directory in [evidence,out]:
    (directory/'SHA256SUMS.txt').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in sorted(directory.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))

"""记录用户确认的高低电平均>=2ns范围；按真实输入筛范围，不改原波形和FAIL。"""
from pathlib import Path
import csv,hashlib,json,datetime
TASK=Path(__file__).resolve().parents[1]
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
truth=read(TASK/'inputs/full_truth.csv');excluded=set();intervals=[]
for r in truth:
    if int(r['fall_ps'])-int(r['rise_ps'])<2000:excluded.add(int(r['pulse_id']))
for left,right in zip(truth,truth[1:]):
    gap=int(right['rise_ps'])-int(left['fall_ps'])
    if gap<2000:
        a,b=int(left['pulse_id']),int(right['pulse_id']);excluded.update([a,b])
        intervals.append(dict(fall_event_id=a,rise_event_id=b,low_gap_ps=gap))
all_ids={int(r['pulse_id']) for r in truth};scope=all_ids-excluded;rows=[]
for delay in [0,250,500]:
    for mode in ['aux_on','noaux']:
        case=TASK/f'results/rtl/lut{delay}/{mode}';s=json.loads((case/'SUMMARY.json').read_text(encoding='utf-8'))
        measured=read(case/'MEASUREMENTS.csv');edges=read(case/'EDGE_RESULTS.csv')
        good=[r for r in measured if r['status']=='MATCHED' and int(r['fall_id']) in scope]
        bad=[r for r in measured if r['status']!='MATCHED']
        assert all(int(r['rise_id']) in excluded and int(r['fall_id']) in excluded for r in bad)
        assert not (set(s['missing_rise_ids']) & scope) and not (set(s['missing_fall_ids']) & scope)
        assert {int(r['fall_id']) for r in good}==scope and len(good)==len(scope)
        assert not any(s[k] for k in ['duplicate_edges','repeat_rise','orphan_fall','merge_range_errors','accepted_out_of_range','candidate_repeat','FIFO_overflow_seen'])
        assert s['FIFO_sequence_equal'] and s['error_FIFO_sequence_equal'] and not s['association_faults'] and not s['pair_faults']
        assert s['polarity_conflict']==(3 if delay==250 else 0)
        rows.append(dict(model_delay_ps=delay,mode=mode,scope_pulses=len(scope),scope_correct=len(good),
                         full_matrix_pass=s['functional_pass'],out_of_scope_mispairs=len(bad),pass_scope=True))
manifest=dict(user_scope_confirmed=True,user_answer='按高低电平均≥2 ns继续',
    recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    high_min_ps=2000,low_min_ps=2000,scope_rule='仅由真实输入决定：排除高电平<2ns的脉冲，以及低电平<2ns间隔的两侧脉冲；不参考测量值筛选',
    full_input_pulses=len(truth),scope_pulse_count=len(scope),scope_ids=sorted(scope),
    excluded_pulse_ids=sorted(excluded),short_low_intervals=intervals,
    original_full_RTL_matrix_pass=False,original_RTL_GATE_sha256=sha(TASK/'results/RTL_GATE.json'),
    stimulus_sha256=sha(TASK/'inputs/full.txt'),truth_sha256=sha(TASK/'inputs/full_truth.csv'),
    original_stimulus_preserved=True,original_failures_preserved=True,thresholds_unchanged=True,
    pass_all=True,results=rows)
assert excluded=={2851,2852,2917,2918,2983,2984,3049,3050},'输入范围审计与已核对的四个短间隔不符'
out=TASK/'results/SCOPED_RTL_GATE.json';assert not out.exists(),'不覆盖已记录范围'
out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('USER_SCOPED_RTL_PASS',len(scope),'of',len(truth),'original overall FAIL retained')

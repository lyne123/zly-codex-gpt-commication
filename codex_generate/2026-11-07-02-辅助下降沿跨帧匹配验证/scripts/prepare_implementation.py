"""通过RTL阶段门后只实现独立候选，正式源码待最终验收后采用。"""
from pathlib import Path
import hashlib,json,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02'
guard=json.loads((TASK/'results/guard/SUMMARY.json').read_text(encoding='utf-8'));assert guard['pass_all']
pwm=json.loads((TASK/'results/PWM_COMPARISON.json').read_text(encoding='utf-8'))
assert all(pwm['E_guarded_lut'+str(d)]['functional_pass'] for d in (0,250,500))
replay=json.loads((TASK/'results/REPLAY_COMPARISON.json').read_text(encoding='utf-8'))
assert replay['real_csv_RTL_equivalent'] and replay['variants']['E_guarded']['double_rise']==0
assert replay['variants']['E_guarded']['changed_existing_choices']==0
assert not (WORK/'implementation').exists(),'禁止覆盖已完成的实现'
previous=ROOT/'codex_generate/.vivado_work/tdc_edge_20261107_01'
for tree in ['aux_compensated.srcs','aux_compensated.gen']:
    shutil.copytree(previous/'registered'/tree,WORK/'registered'/tree)
shutil.copytree(previous/'ip_cache',WORK/'ip_cache')
shutil.copy2(previous/'production_AD23.dcp',WORK/'production_AD23.dcp')
for name in ['compensation_params.tcl','combine_AD23.xdc']:shutil.copy2(TASK/'inputs'/name,WORK/name)
shutil.copy2(TASK/'scripts/build_candidate.tcl',WORK/'build_candidate.tcl')
record=dict(candidate='E_guarded',RTL_gate_pass=True,real_CSV_recovery=True,guard_cases=262144,
    formal_RTL_modified=False,compensation_recalculated=False,known_scope='辅助确认无状态回退；原有效帧优先；器件SDF与时序尚待验收')
(TASK/'results/RTL_STAGE_GATE.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print('CANDIDATE_IMPLEMENTATION_PREPARED; FORMAL_BASELINE_UNCHANGED')

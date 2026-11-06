"""H通过RTL后仅实现一次，保留G失败证据，以G实际路由增量复用。"""
from pathlib import Path
import json,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
assert json.loads((TASK/'results/H_registered_match/RTL_STAGE_GATE.json').read_text(encoding='utf-8'))['pass_all']
assert not (WORK/'implementation_H').exists(),'已有实现禁止覆盖'
text=(TASK/'scripts/build_G.tcl').read_text(encoding='utf-8')
text=text.replace('set out $work/implementation_G','set out $work/implementation_H').replace('$work/G_precompute/','$work/H_registered_match/')
text=text.replace('read_checkpoint -incremental $work/reference_F.dcp','read_checkpoint -incremental $work/implementation_G/corrected_routed.dcp')
(TASK/'scripts/build_H.tcl').write_text(text,encoding='utf-8');shutil.copy2(TASK/'scripts/build_H.tcl',WORK/'build_H.tcl')
print('H_BUILD_PREPARED; same constraints; increment from G')

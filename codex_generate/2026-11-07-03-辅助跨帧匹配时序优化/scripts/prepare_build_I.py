"""只有整组延迟等价验证通过，才实现专用确认流水候选。"""
from pathlib import Path
import json,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
assert json.loads((TASK/'results/I_confirmation_pipe/RTL_STAGE_GATE.json').read_text(encoding='utf-8'))['pass_all']
assert not (WORK/'implementation_I').exists(),'已有实现禁止覆盖'
text=(TASK/'scripts/build_G.tcl').read_text(encoding='utf-8')
text=text.replace('set out $work/implementation_G','set out $work/implementation_I').replace('$work/G_precompute/','$work/I_confirmation_pipe/')
text=text.replace('read_checkpoint -incremental $work/reference_F.dcp','read_checkpoint -incremental $work/implementation_fanout/corrected_routed.dcp')
text=text.replace('frequency_mhz=500"','frequency_mhz=500\\nadded_output_cycles=1"')
(TASK/'scripts/build_I.tcl').write_text(text,encoding='utf-8');shutil.copy2(TASK/'scripts/build_I.tcl',WORK/'build_I.tcl')
print('I_BUILD_PREPARED; fine/candidate/timestamp/width/error +1; same data; coarse snapshot aligned')

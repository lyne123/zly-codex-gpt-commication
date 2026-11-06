"""仅针对H报告的晚到ready再实现等价末级选择，不扫描种子或参数。"""
from pathlib import Path
import json,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
assert json.loads((TASK/'results/H2_late_ready/RTL_STAGE_GATE.json').read_text(encoding='utf-8'))['pass_all']
assert not (WORK/'implementation_H2').exists(),'已有实现禁止覆盖'
text=(TASK/'scripts/build_H.tcl').read_text(encoding='utf-8')
text=text.replace('set out $work/implementation_H','set out $work/implementation_H2').replace('$work/H_registered_match/','$work/H2_late_ready/')
# G的两个FIFO模块都满足时序，继续使用同一G增量参考，避免沿用H的FIFO负路径。
(TASK/'scripts/build_H2.tcl').write_text(text,encoding='utf-8');shutil.copy2(TASK/'scripts/build_H2.tcl',WORK/'build_H2.tcl')
print('H2_BUILD_PREPARED; same constraints and G incremental reference')

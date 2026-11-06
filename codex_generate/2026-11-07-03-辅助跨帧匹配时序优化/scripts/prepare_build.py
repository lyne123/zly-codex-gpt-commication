"""仅在RTL门通过后，复用原IP与F路由作为增量参考实现候选。"""
from pathlib import Path
import json,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
PREV=ROOT/'codex_generate/2026-11-07-02-辅助下降沿跨帧匹配验证'
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
assert json.loads((TASK/'results/RTL_STAGE_GATE.json').read_text(encoding='utf-8'))['pass_all']
assert not (WORK/'implementation_G').exists(),'已有实现禁止覆盖'
oldwork=ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02'
for folder in ['registered','ip_cache']:shutil.copytree(oldwork/folder,WORK/folder)
shutil.copy2(PREV/'results/implementation_F/corrected_routed.dcp',WORK/'reference_F.dcp')
shutil.copy2(oldwork/'production_AD23.dcp',WORK/'production_AD23.dcp')
for name in ['compensation_params.tcl','combine_AD23.xdc']:shutil.copy2(TASK/'inputs'/name,WORK/name)
text=(PREV/'scripts/build_factored.tcl').read_text(encoding='utf-8-sig')
text=text.replace('set out $work/implementation_F','set out $work/implementation_G').replace('$work/F_factored/','$work/G_precompute/')
text=text.replace('read_checkpoint -incremental $work/production_AD23.dcp','read_checkpoint -incremental $work/reference_F.dcp')
text=text.replace('AUXFALL_','AUXMATCH_')
(TASK/'scripts/build_G.tcl').write_text(text,encoding='utf-8')
shutil.copy2(TASK/'scripts/build_G.tcl',WORK/'build_G.tcl')
print('G_BUILD_PREPARED; increment from F; same constraints and parameters')

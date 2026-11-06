"""复用已验证的三个数据网定向复制，仅针对最后的early ready同拍寄存实现。"""
from pathlib import Path
import json,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
assert json.loads((TASK/'results/H3_ready_precompute/RTL_STAGE_GATE.json').read_text(encoding='utf-8'))['pass_all']
assert not (WORK/'implementation_H3').exists(),'已有实现禁止覆盖'
text=(TASK/'scripts/build_H2.tcl').read_text(encoding='utf-8')
text=text.replace('set out $work/implementation_H2','set out $work/implementation_H3').replace('$work/H2_late_ready/','$work/H3_ready_precompute/')
text=text.replace('read_checkpoint -incremental $work/implementation_G/corrected_routed.dcp','read_checkpoint -incremental $work/implementation_physical/corrected_routed.dcp')
marker='write_checkpoint $out/corrected_placed.dcp'
block='''# 保留H2实际负路径已验证有效的三数据网定向复制；只在合法的布局后执行。
set target_nets {}
foreach qname [list {u_tdc_fine_layer/g_aux_4phase.rise_previous_single_q_reg/Q} {u_tdc_fine_layer/pack0_d1_reg[8]/Q} {u_tdc_fine_layer/pack90_d2_reg[9]/Q}] {
    set qpin [get_pins -quiet -hier -filter "NAME == $qname"]
    if {![llength $qpin]} {error "物理目标Q引脚不存在：$qname"}
    foreach n [get_nets -of_objects $qpin] {lappend target_nets [get_property NAME $n]}
}
phys_opt_design -force_replication_on_nets [get_nets [lsort -unique $target_nets]]
phys_opt_design -critical_pin_opt -placement_opt
'''
assert text.count(marker)==1;text=text.replace(marker,block+marker)
text=text.replace('route_design -directive Explore\nphys_opt_design -directive AggressiveExplore','route_design -directive Explore')
(TASK/'scripts/build_H3.tcl').write_text(text,encoding='utf-8');shutil.copy2(TASK/'scripts/build_H3.tcl',WORK/'build_H3.tcl')
print('H3_BUILD_PREPARED; no new constraints or pipeline; prior successful physical targeting reused')

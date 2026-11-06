# 使用H2已有布局检查点；目标由H2实际路由负路径确定，进行一次合法的布局后定向复制。
# 不重综合，不retime，不改变时钟、约束、RTL或流水线延迟。
set_param general.maxThreads 1
set work [file dirname [file normalize [info script]]]
cd $work
set out $work/implementation_physical
if {[file exists $out]} {error "禁止覆盖已有物理优化证据"}
file mkdir $out
source $work/export_timing_proc.tcl
open_checkpoint $work/implementation_H2/corrected_placed.dcp
set nets {}
set fd [open $out/replication_targets.csv w]
puts $fd "startpoint,net"
foreach start [list {u_tdc_fine_layer/g_aux_4phase.rise_previous_single_q_reg/C} {u_tdc_fine_layer/pack0_d1_reg[8]/C} {u_tdc_fine_layer/pack90_d2_reg[9]/C}] {
    regsub {/C$} $start {/Q} qname
    set qpin [get_pins -quiet -hier -filter "NAME == $qname"]
    if {![llength $qpin]} {error "无法读取真实起点Q引脚：$qname"}
    set net [get_nets -of_objects $qpin]
    foreach n $net {lappend nets [get_property NAME $n];puts $fd "$start,[get_property NAME $n]"}
}
close $fd
set nets [lsort -unique $nets]
if {[llength $nets]!=3} {error "负路径集合与预期三起点不同，停止盲目物理优化"}
puts "TARGETED_NEGATIVE_STARTPOINT_NETS=$nets"
phys_opt_design -force_replication_on_nets [get_nets $nets]
phys_opt_design -critical_pin_opt -placement_opt
route_design -directive Explore
write_checkpoint $out/corrected_routed.dcp
export_timing $out/after
report_route_status -file $out/after/route_status.rpt
report_drc -file $out/after/drc.rpt
write_debug_probes $out/Corrected.ltx
write_xdc $out/effective_constraints.xdc
write_verilog -mode timesim -sdf_anno false $out/post_route_timing.v
write_sdf -process_corner slow $out/post_route_max.sdf
set bad 0
foreach delay {max min} {
    foreach p [get_timing_paths -quiet -delay_type $delay -slack_lesser_than 0 -max_paths 10000 -nworst 1] {
        set end [get_property ENDPOINT_PIN $p]
        if {![string match u_ila* $end] && ![string match dbg_hub/* $end]} {incr bad}
    }
}
set fd [open $out/TIMING_GATE.txt w]
puts $fd "core_negative_endpoints=$bad\nbit_generated=0\nformal_rtl_modified=0\nfrequency_mhz=500\nadded_output_cycles=0"
close $fd
if {$bad} {error "CORE_TIMING_FAIL：本次定向物理优化未通过"}
puts "TARGETED_PHYSICAL_CORE_PASS"
close_design


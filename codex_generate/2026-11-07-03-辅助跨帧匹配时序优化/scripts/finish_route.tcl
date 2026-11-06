# H3定向复制后的实际路由仅剩一个38ps核心缺口；执行合法的路由后局部放置/布线收尾。
set_param general.maxThreads 1
set work [file dirname [file normalize [info script]]]
cd $work
set out $work/implementation_closed
if {[file exists $out]} {error "禁止覆盖路由后收尾结果"}
file mkdir $out
source $work/export_timing_proc.tcl
open_checkpoint $work/implementation_H3_physical/corrected_routed.dcp
phys_opt_design -placement_opt -routing_opt
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
if {$bad} {error "CORE_TIMING_FAIL：保留路由后收尾失败证据"}
puts "CORE_TIMING_CLOSED"
close_design

# 使用I已有布局检查点；仅对实测STA剩余的FIFO计数bit0和前端90°类型bit9两个起点做物理优化。
# 不重综合、不改变FIFO IP配置或逻辑，不retime、不改时钟例外；保持I已验证的一拍延迟。
set_param general.maxThreads 1
set work [file dirname [file normalize [info script]]]
cd $work
set out $work/implementation_I_physical
if {[file exists $out]} {error "禁止覆盖已有物理优化证据"}
file mkdir $out
source $work/export_timing_proc.tcl
open_checkpoint $work/implementation_I/corrected_placed.dcp
set nets {}
set fd [open $out/replication_targets.csv w]
puts $fd "startpoint,net"
foreach start [list {u_fifo_tdc_result/U0/inst_fifo_gen/gconvfifo.rf/grf.rf/gntv_or_sync_fifo.gl0.wr/wpntr/gic0.gc0.count_d1_reg[0]/C} {u_tdc_fine_layer/pack90_d2_reg[9]/C}] {
    regsub {/C$} $start {/Q} qname
    set qpin [get_pins -quiet -hier -filter "NAME == $qname"]
    if {![llength $qpin]} {error "无法读取真实起点Q引脚：$qname"}
    set net [get_nets -of_objects $qpin]
    foreach n $net {lappend nets [get_property NAME $n];puts $fd "$start,[get_property NAME $n]"}
}
close $fd
set nets [lsort -unique $nets]
if {[llength $nets]!=2} {error "负路径集合与预期两起点不同，停止盲目物理优化"}
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
puts $fd "core_negative_endpoints=$bad\nbit_generated=0\nformal_rtl_modified=0\nfrequency_mhz=500\nadded_output_cycles=1"
close $fd
if {$bad} {error "CORE_TIMING_FAIL：本次定向物理优化未通过"}
puts "TARGETED_PHYSICAL_CORE_PASS"
close_design




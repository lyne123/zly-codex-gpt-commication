# 从I已完成综合DCP继续，恢复实际AD23生产版已验证的FIFO位置；不重新综合。
set_param general.maxThreads 1
set_param ips.addSpecialDataToCacheID 0
set work [file dirname [file normalize [info script]]]
cd $work
set out $work/implementation_fifo_placed
if {[file exists $out]} {error "禁止覆盖FIFO位置复用结果"}
file mkdir $out
source $work/export_timing_proc.tcl
open_checkpoint $work/implementation_I/corrected_synth.dcp
config_ip_cache -use_cache_location $work/ip_cache
read_xdc $work/combine_AD23.xdc
opt_design -directive Explore
opt_design -bram_power_opt
read_checkpoint -incremental $work/production_AD23.dcp
set fd [open $work/production_fifo_placement.csv r]
gets $fd header
set trace [open $out/placement_applied.csv w]
puts $trace "cell,reference_type,current_type,loc,bel,status"
set count 0
while {[gets $fd line]>=0} {
    if {$line eq ""} {continue}
    lassign [split [string trim $line] ,] name ref loc bel
    set cell [get_cells -quiet -hier -filter "NAME == $name"]
    if {![llength $cell]} {puts $trace "$name,$ref,,${loc},${bel},not_present";continue}
    set current_ref [get_property REF_NAME $cell]
    if {$current_ref ne $ref} {puts $trace "$name,$ref,$current_ref,$loc,$bel,type_different";continue}
    if {$loc eq "" || $bel eq ""} {error "参考位置为空：$name"}
    set_property LOC $loc $cell
    set_property BEL [lindex [split $bel .] end] $cell
    puts $trace "$name,$ref,$current_ref,$loc,$bel,applied"
    incr count
}
close $fd
close $trace
if {$count<100} {error "FIFO物理参考匹配不足，停止而非猜测位置"}
puts "FIFO_PLACEMENT_RESTORED=$count"
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
# 前端仅剩的9ps数据网使用已验证的定向物理复制；不复制FIFO计数器。
set qpin [get_pins -quiet -hier -filter {NAME == u_tdc_fine_layer/pack90_d2_reg[9]/Q}]
if {![llength $qpin]} {error "前端目标不存在"}
phys_opt_design -force_replication_on_nets [get_nets -of_objects $qpin]
write_checkpoint $out/corrected_placed.dcp
route_design -directive Explore
phys_opt_design -directive AggressiveExplore
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
puts $fd "core_negative_endpoints=$bad\nbit_generated=0\nformal_rtl_modified=0\nfrequency_mhz=500\nadded_output_cycles=1\nFIFO_IP_configuration_changed=0"
close $fd
if {$bad} {error "CORE_TIMING_FAIL：FIFO位置复用未通过"}
puts "CORE_TIMING_CLOSED_WITH_ORIGINAL_FIFO_PLACEMENT"
close_design

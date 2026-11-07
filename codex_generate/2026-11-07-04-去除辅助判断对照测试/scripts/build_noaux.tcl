# 同一器件、时钟、约束和IP配置，仅将辅助确认参数固定为0；不访问硬件。
set_param general.maxThreads 1
set_param ips.addSpecialDataToCacheID 0
set work [file dirname [file normalize [info script]]]
cd $work
if {![file exists $work/RTL_APPROVED.flag]} {error "RTL门未通过，不进行综合实现"}
set out $work/implementation
if {[file exists $out]} {error "已有实现目录，不覆盖失败或成功证据"}
file mkdir $out
source $work/export_timing_proc.tcl
create_project -in_memory -part xc7k325tffg900-2
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
config_ip_cache -use_cache_location $work/../tdc_auxmatch_20261107_03/ip_cache
read_verilog [glob $work/rtl/*.v]
foreach ip {clk_wiz_0 fifo_tdc_result ila_2 ila_3} {
    read_ip $work/registered/aux_compensated.srcs/sources_1/ip/$ip/$ip.xci
    generate_target all [get_ips $ip]
    synth_ip [get_ips $ip]
}
source -encoding utf-8 $work/inputs/compensation_params.tcl
set generics [concat $compensation_generics {ENABLE_AUX_CONFIRM=0}]
puts "NOAUX_FROZEN_GENERICS=$generics"
synth_design -top tdc_meas_top -part xc7k325tffg900-2 -directive PerformanceOptimized -fsm_extraction one_hot -keep_equivalent_registers -resource_sharing off -no_lc -shreg_min_size 5 -generic $generics
write_checkpoint $out/NoAux_synth.dcp
read_xdc $work/inputs/combine_AD23.xdc
opt_design -directive Explore
opt_design -bram_power_opt
# 复用指定提交最终DCP作为增量位置参考，避免改变已经验证的FIFO布局。
read_checkpoint -incremental $work/reference_corrected.dcp
set f [open $work/inputs/production_fifo_placement.csv r]
gets $f header
set placements {}
while {[gets $f line]>=0} {
    if {$line eq ""} {continue}
    lassign [split [string trim $line] ,] name ref loc bel
    if {$ref in {VCC GND}} {continue}
    set c [get_cells -quiet -hier -filter "NAME == $name"]
    if {[llength $c]!=1 || [get_property REF_NAME $c] ne $ref} {error "FIFO位置参考不匹配：$name"}
    set_property BEL [lindex [split $bel .] end] $c
    lappend placements [list $c $name $loc $bel]
}
close $f
set f [open $out/FIFO_PLACEMENT.csv w]
puts $f "cell,loc,bel"
foreach item $placements {
    lassign $item c name loc bel
    set_property LOC $loc $c
    puts $f "$name,$loc,$bel"
}
close $f
if {[llength $placements]!=578} {error "FIFO位置恢复数不是已验证的578"}
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
write_checkpoint $out/NoAux_placed.dcp
route_design -directive Explore
phys_opt_design -directive AggressiveExplore
write_checkpoint $out/NoAux_routed.dcp
export_timing $out/after
report_route_status -file $out/after/route_status.rpt
report_drc -file $out/after/drc.rpt
report_utilization -hierarchical -file $out/after/utilization.rpt
write_xdc $out/effective_constraints.xdc
if {[get_property PACKAGE_PIN [get_ports pwm_in]] ne "AD23"} {error "PWM输入引脚不匹配"}
set bad_setup 0
set bad_hold 0
foreach delay {max min} {
    foreach p [get_timing_paths -quiet -delay_type $delay -slack_lesser_than 0 -max_paths 10000 -nworst 1] {
        set endpoint [get_property ENDPOINT_PIN $p]
        if {![string match u_ila* $endpoint] && ![string match dbg_hub/* $endpoint]} {
            if {$delay eq "max"} {incr bad_setup} else {incr bad_hold}
        }
    }
}
set f [open $out/TIMING_GATE.txt w]
puts $f "core_setup_negative=$bad_setup\ncore_hold_negative=$bad_hold\nENABLE_AUX_CONFIRM=0\nadditional_cycles_vs_Corrected=0\nhardware_programmed=0"
close $f
if {$bad_setup || $bad_hold} {error "NOAUX_CORE_TIMING_FAIL：保留证据，不运行SDF或生成BIT"}
write_verilog -mode timesim -sdf_anno false $out/post_route_timing.v
write_sdf -process_corner slow $out/post_route_max.sdf
write_debug_probes $out/NoAux.ltx
puts "NOAUX_CORE_TIMING_PASS_NO_BIT_YET"
close_design

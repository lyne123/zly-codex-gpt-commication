# 全部运行文件使用真实ASCII目录；正式工程和生产BIT只读。
set_param general.maxThreads 1
# 与已验证Hub缓存的Vivado生成脚本保持相同缓存键规则，只影响IP缓存识别。
set_param ips.addSpecialDataToCacheID 0
set work [file dirname [file normalize [info script]]]
cd $work
set out $work/results
file mkdir $out
if {[file exists $out/debug_routed.dcp]} {error "已有本次实现，禁止重复覆盖"}

proc export_timing {folder} {
    file mkdir $folder
    update_timing -full
    report_timing_summary -delay_type min_max -report_unconstrained -file $folder/timing_summary.rpt
    report_timing -delay_type max -max_paths 40 -path_type full_clock_expanded -file $folder/setup_top40.rpt
    report_timing -delay_type min -max_paths 20 -file $folder/hold_top20.rpt
    set fd [open $folder/negative_setup.csv w]
    puts $fd "slack_ns,startpoint,endpoint"
    foreach p [get_timing_paths -quiet -delay_type max -slack_lesser_than 0 -max_paths 10000 -nworst 1] {
        puts $fd "[get_property SLACK $p],[get_property STARTPOINT_PIN $p],[get_property ENDPOINT_PIN $p]"
    }
    close $fd
    set fd [open $folder/negative_hold.csv w]
    puts $fd "slack_ns,startpoint,endpoint"
    foreach p [get_timing_paths -quiet -delay_type min -slack_lesser_than 0 -max_paths 10000 -nworst 1] {
        puts $fd "[get_property SLACK $p],[get_property STARTPOINT_PIN $p],[get_property ENDPOINT_PIN $p]"
    }
    close $fd
    set fd [open $folder/core_timing.csv w]
    puts $fd "module,delay_type,slack_ns,startpoint,endpoint"
    foreach module {u_tdc_fine_layer u_tdc_time_candicate u_tdc_time_locate u_tdc_time_merge u_fifo_tdc_result u_fifo_tdc_error} {
        set cells [get_cells -quiet -hier -filter "NAME =~ $module/*"]
        foreach delay {max min} {
            set p [get_timing_paths -quiet -to $cells -delay_type $delay -max_paths 1]
            if {[llength $p]} {puts $fd "$module,$delay,[get_property SLACK $p],[get_property STARTPOINT_PIN $p],[get_property ENDPOINT_PIN $p]"}
        }
    }
    close $fd
    report_clocks -file $folder/clocks.rpt
    report_exceptions -file $folder/exceptions.rpt
}

if {![file exists $work/debug_synth.dcp]} {
puts "DEBUG_STAGE=PRODUCTION_BASELINE"
open_checkpoint $work/production_AD23.dcp
if {[get_property PACKAGE_PIN [get_ports pwm_in]] ne "AD23"} {error "参考不是实际AD23版本"}
export_timing $out/before
set fd [open $out/before/measurement_cells.csv w]
puts $fd "cell,ref,loc,bel"
foreach c [get_cells -hier -filter {IS_PRIMITIVE && (NAME =~ u_tdc* || NAME =~ u_fifo_tdc*)}] {
    puts $fd "[get_property NAME $c],[get_property REF_NAME $c],[get_property LOC $c],[get_property BEL $c]"
}
close $fd
close_design

puts "DEBUG_STAGE=IP_PREPARATION"
create_project -in_memory -part xc7k325tffg900-2
set_property target_language Verilog [current_project]
config_ip_cache -use_cache_location $work/ip_cache
read_verilog [glob $work/rtl/*.v]
foreach ip {clk_wiz_0 fifo_tdc_result ila_3} {
    read_ip $work/registered/aux_compensated.srcs/sources_1/ip/$ip/$ip.xci
    synth_ip [get_ips $ip]
}
file mkdir $work/new_ip
create_ip -name ila -vendor xilinx.com -library ip -version 6.2 -module_name ila_edge_debug -dir $work/new_ip
set_property -dict [list CONFIG.C_NUM_OF_PROBES {8} CONFIG.C_DATA_DEPTH {1024} CONFIG.C_INPUT_PIPE_STAGES {4} \
    CONFIG.C_PROBE0_WIDTH {32} CONFIG.C_PROBE1_WIDTH {40} CONFIG.C_PROBE2_WIDTH {64} CONFIG.C_PROBE3_WIDTH {40} \
    CONFIG.C_PROBE4_WIDTH {21} CONFIG.C_PROBE5_WIDTH {21} CONFIG.C_PROBE6_WIDTH {64} CONFIG.C_PROBE7_WIDTH {32}] [get_ips ila_edge_debug]
# 类型0为数据及触发，类型1为仅数据。只让控制总线参与比较，减少500MHz触发逻辑。
for {set p 1} {$p<8} {incr p} {set_property CONFIG.C_PROBE${p}_TYPE 1 [get_ips ila_edge_debug]}
generate_target all [get_ips ila_edge_debug]
synth_ip [get_ips ila_edge_debug]
source -encoding utf-8 $work/compensation_params.tcl
puts "DEBUG_STAGE=TOP_SYNTHESIS"
synth_design -top tdc_meas_top -part xc7k325tffg900-2 -directive PerformanceOptimized -fsm_extraction one_hot -keep_equivalent_registers -resource_sharing off -no_lc -shreg_min_size 5 -generic $compensation_generics
write_checkpoint $work/debug_synth.dcp
} else {
    puts "DEBUG_STAGE=RESUME_COMPLETED_SYNTHESIS"
    open_checkpoint $work/debug_synth.dcp
    config_ip_cache -use_cache_location $work/ip_cache
}
read_xdc $work/combine_AD23.xdc
puts "DEBUG_STAGE=IMPLEMENTATION"
opt_design -directive Explore
opt_design -bram_power_opt
write_checkpoint $work/debug_opt.dcp
read_checkpoint -incremental $work/production_AD23.dcp
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
write_checkpoint $work/debug_place.dcp
route_design -directive Explore
phys_opt_design -directive AggressiveExplore
write_checkpoint $out/debug_routed.dcp
export_timing $out/after
report_route_status -file $out/after/route_status.rpt
report_drc -file $out/after/drc.rpt
report_cdc -details -file $out/after/cdc.rpt
report_utilization -hierarchical -file $out/after/utilization.rpt
write_debug_probes $out/ILA_DEBUG.ltx
write_xdc $out/effective_constraints.xdc
# 负路径只允许落在调试逻辑；只要有测量端点负裕量，就不生成BIT。
set bad_core 0
foreach delay {max min} {
    foreach p [get_timing_paths -quiet -delay_type $delay -slack_lesser_than 0 -max_paths 10000 -nworst 1] {
        set end [get_property ENDPOINT_PIN $p]
        if {![string match u_ila* $end] && ![string match debug_* $end] && ![string match dbg_hub/* $end]} {incr bad_core}
    }
}
# 调试采集本身也必须有可靠时序；不能使用有违例的探针声称定位成功。
set bad_debug [llength [get_timing_paths -quiet -delay_type max -slack_lesser_than 0 -max_paths 1]]
set bad_hold [llength [get_timing_paths -quiet -delay_type min -slack_lesser_than 0 -max_paths 1]]
set fd [open $out/TIMING_GATE.txt w]
puts $fd "core_negative_paths=$bad_core\nany_negative_setup=$bad_debug\nany_negative_hold=$bad_hold\nproduction_rtl_modified=0\nmeasurement_algorithm_modified=0"
close $fd
if {$bad_core || $bad_debug || $bad_hold} {error "DEBUG_TIMING_GATE_FAIL：已保留报告，未生成BIT；禁止强行忽略时序"}
if {[get_property PACKAGE_PIN [get_ports pwm_in]] ne "AD23"} {error "Debug引脚不是AD23"}
write_bitstream $out/ILA_DEBUG.bit
puts "DEBUG_BIT_COMPLETE"
close_design
